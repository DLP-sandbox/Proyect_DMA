"""
Agente de Riesgo & Position Sizing — calcula el R/R cuantitativo,
stop técnico, target y sizing sugerido. Actúa como multiplicador del score.
"""
import anthropic
import numpy as np

from agents.base import BaseAgent, AgentReport
from data.market_data import get_price_history, compute_technical_indicators, get_company_info


SYSTEM_PROMPT = """Eres el Risk Manager de un hedge fund de élite especializado en HOLD DE CALIDAD A LARGO PLAZO.

Tu filosofía DUAL:
- INVERSIÓN TÁCTICA (corto plazo): requiere R/R ≥ 2:1 para tener edge estadístico
- HOLD DE CALIDAD LP (3-7 años): R/R inmediato puede ser tight (1.2-1.8:1) si la empresa es excepcional (moat amplio, ROIC alto, management excelente). Compounders como Microsoft, Visa, ASML rara vez ofrecen R/R 3:1 inmediato pero compoundean a 15-20% anual durante décadas.

Tu trabajo es:
1. Identificar el TIPO de oportunidad (trade táctico vs hold LP)
2. Cuantificar el riesgo en términos absolutos (volatilidad, drawdown)
3. Identificar la DIRECCIÓN DE LA ASIMETRÍA: ¿el upside es mayor que el downside, igual, o el riesgo es a la baja?

Calculas y evalúas:
1. NIVEL DE PROTECCIÓN: Basado en el soporte técnico más cercano (mínimo swing reciente, MA 50W, o nivel de base)
2. TARGET PRICE: Basado en la resistencia técnica + análisis de valuación fundamental
3. RISK/REWARD RATIO: (Target - Precio actual) / (Precio actual - Stop)
4. VOLATILIDAD: ATR como % del precio — determina el tamaño de posición
5. PORTFOLIO FIT: Correlación con el mercado (beta), diversificación de factor
6. SCENARIO ANALYSIS: Qué pasa en escenario bajista de mercado -20%?
7. POSITION SIZING: Kelly Criterion modificado — % del portafolio que tiene sentido arriesgar
8. DIRECCIÓN DE LA ASIMETRÍA: ¿upside potencial supera al downside? (es lo más importante)

Criterios de SCORING (escala continua 0-100, granular, sin clustering):

- 82-95: Excelente — R/R muy favorable (>2.5:1) + volatilidad gestionable + asimetría clara al alza.
- 67-81: Bueno — R/R aceptable (1.5-2.5:1) o empresa de calidad LP que justifica R/R tight.
- 52-66: Mediano — R/R justo (1-1.5:1), requiere otras razones (calidad, catalizador) para entrar.
- 35-51: Pobre — R/R desfavorable o volatilidad alta, pero no veto absoluto.
- 20-34: Asimetría negativa material — downside supera upside, esperar mejor entrada.
- <20: Muy pobre — downside ≥ 2× upside, claramente desfavorable.

REGLA ANTI-CLUSTERING: dos análisis distintos NUNCA deben tener exactamente el mismo score. No te ancles en 28, 35, 65, 72. Da scores precisos basados en el R/R real cuantitativo (ej: si R/R=1.8 y vol manejable, podría ser 71; si R/R=2.1 con vol alta, podría ser 67).

IMPORTANTE: NO existe un cap automático de 35 puntos. Una empresa best-in-class de calidad LP con R/R 1.5:1 puede legítimamente puntuar 70+ porque la calidad estructural compensa.

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100, refleja la gestionabilidad TOTAL del riesgo>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis de riesgo y sizing en 2 párrafos>",
  "pros": ["<ventaja de riesgo 1>", "<ventaja de riesgo 2>"],
  "cons": ["<riesgo 1>", "<riesgo 2>"],
  "key_metrics": {
    "entry_price": "<precio sugerido de entrada>",
    "stop_loss": "<precio del nivel de protección técnico>",
    "target_price": "<precio objetivo>",
    "risk_reward": "<X:1>",
    "max_loss_pct": "<-X% desde entrada al stop>",
    "potential_gain_pct": "<+X% desde entrada al target>",
    "position_size_pct": "<X% del portafolio sugerido>",
    "volatility_atr_pct": "<X% ATR diario>"
  },
  "sub_scores": {
    "risk_reward_quality": <0-40>,
    "volatility_manageability": <0-30>,
    "downside_protection": <0-30>
  },
  "asymmetry_direction": "<upside|downside|balanced>",
  "asymmetry_strength": "<strong|moderate|weak>",
  "stop_rationale": "<por qué ese nivel es el precio de protección correcto>"
}
```

Sobre `asymmetry_direction` y `asymmetry_strength`:
- "upside" + "strong" → upside ≥ 2x downside (clara oportunidad asimétrica al alza)
- "upside" + "moderate" → upside > downside pero no dramático
- "balanced" → upside ≈ downside (no hay edge claro de asimetría)
- "downside" + "strong" → downside ≥ 2x upside (riesgo asimétrico negativo, evitar)
- "downside" + "moderate" → riesgo a la baja modesto pero presente

Sé honesto: si la empresa es de calidad excepcional pero el precio actual está cerca del target, la asimetría puede ser "balanced" o incluso "downside" — eso NO descalifica el hold LP, solo informa el timing."""


class RiskAgent(BaseAgent):
    name = "Riesgo & Sizing"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            df = get_price_history(ticker, period="1y")
            info = get_company_info(ticker)
            ind = compute_technical_indicators(df) if not df.empty else {}

            # Calcular métricas cuantitativas de riesgo pre-análisis
            risk_metrics = self._compute_risk_metrics(df, ind, info)

            user_message = self._build_message(ticker, info, ind, risk_metrics)
            result = self._call_claude(SYSTEM_PROMPT, user_message)

            if "error" in result and "score" not in result:
                return self._safe_report(ticker, result.get("error", "Error"))

            # Extraer niveles clave para uso del dashboard
            km = result.get("key_metrics", {})

            return AgentReport(
                agent_name=self.name,
                score=float(result.get("score", 50)),
                analysis=result.get("analysis", ""),
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                key_metrics=km,
                conviction=result.get("conviction", "MEDIUM"),
                sub_scores=result.get("sub_scores", {}),
                raw_data={
                    "stop_rationale": result.get("stop_rationale", ""),
                    "asymmetry_direction": result.get("asymmetry_direction"),
                    "asymmetry_strength": result.get("asymmetry_strength"),
                    "entry_price":  km.get("entry_price"),
                    "stop_loss":    km.get("stop_loss"),
                    "target_price": km.get("target_price"),
                    "risk_reward":  km.get("risk_reward"),
                    "position_size_pct": km.get("position_size_pct"),
                    "computed_risk": risk_metrics,
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _compute_risk_metrics(self, df, ind, info) -> dict:
        """Pre-calcula métricas cuantitativas para el agente."""
        metrics = {}
        if df.empty or not ind:
            return metrics

        close = df["Close"]
        price = float(close.iloc[-1])
        metrics["current_price"] = price

        # ATR
        atr = ind.get("atr_14", price * 0.02)
        metrics["atr"] = atr
        metrics["atr_pct"] = atr / price * 100

        # Stop técnico: mínimo de las últimas 10 semanas
        low_10w = float(df["Low"].tail(50).min())
        metrics["swing_low_10w"] = low_10w
        metrics["stop_suggested"] = round(low_10w * 0.98, 2)  # 2% bajo el swing low
        metrics["risk_pct"] = (price - metrics["stop_suggested"]) / price * 100

        # Resistencia: 52W high o 25% arriba del precio
        high_52w = ind.get("52w_high", price * 1.25)
        if price < high_52w * 0.85:
            metrics["target_suggested"] = round(high_52w, 2)
        else:
            metrics["target_suggested"] = round(price * 1.25, 2)  # 25% upside si ya está cerca del high

        metrics["reward_pct"] = (metrics["target_suggested"] - price) / price * 100
        if metrics["risk_pct"] > 0:
            metrics["rr_ratio"] = metrics["reward_pct"] / metrics["risk_pct"]
        else:
            metrics["rr_ratio"] = 0

        # Position sizing (1% risk del portfolio por trade)
        risk_per_share = price - metrics["stop_suggested"]
        if risk_per_share > 0:
            shares_per_1k_risk = 1000 / risk_per_share
            pos_value = shares_per_1k_risk * price
            metrics["position_size_at_1pct_risk"] = pos_value  # valor en USD para 1% de riesgo en $100K portfolio

        metrics["beta"] = info.get("beta", 1.0)
        metrics["implied_portfolio_pct"] = min(round(1 / metrics["rr_ratio"] * 5, 1), 10) if metrics.get("rr_ratio", 0) > 0 else 0

        return metrics

    def _build_message(self, ticker, info, ind, risk) -> str:
        price = risk.get("current_price", ind.get("current_price", "N/A"))

        lines = [
            f"# Análisis de Riesgo & Sizing: {ticker} — {info.get('name', ticker)}",
            f"**Precio actual:** ${price}",
            f"**Beta:** {info.get('beta', 1.0):.2f}",
            "",
            "## Métricas de Riesgo Pre-Calculadas",
            f"- ATR 14 días: ${risk.get('atr', 'N/A'):.2f} ({risk.get('atr_pct', 0):.1f}% del precio)" if risk.get('atr') else "- ATR: N/A",
            f"- Swing Low 10W: ${risk.get('swing_low_10w', 'N/A'):.2f}",
            f"- Nivel de Protección Sugerido (cuantitativo): ${risk.get('stop_suggested', 'N/A'):.2f}",
            f"- Riesgo al nivel de protección: -{risk.get('risk_pct', 0):.1f}%",
            f"- Target Sugerido (cuantitativo): ${risk.get('target_suggested', 'N/A'):.2f}",
            f"- Upside potencial: +{risk.get('reward_pct', 0):.1f}%",
            f"- R/R Ratio (cuantitativo): {risk.get('rr_ratio', 0):.2f}:1",
            f"- Portfolio % sugerido (cuantitativo): {risk.get('implied_portfolio_pct', 0):.1f}%",
            "",
            "## Indicadores Técnicos Relevantes",
            f"- RSI 14: {ind.get('rsi_14', 'N/A'):.1f}" if ind.get('rsi_14') else "- RSI 14: N/A",
            f"- SMA 50: ${ind.get('sma_50', 'N/A'):.2f}" if ind.get('sma_50') else "- SMA 50: N/A",
            f"- SMA 200: ${ind.get('sma_200', 'N/A'):.2f}" if ind.get('sma_200') else "- SMA 200: N/A",
            f"- Stage: {ind.get('stage', 'N/A')}",
            f"- Distancia 52W High: {ind.get('pct_from_52w_high', 0):.1f}%",
            f"- 52W High: ${ind.get('52w_high', 'N/A'):.2f}" if ind.get('52w_high') else "- 52W High: N/A",
            f"- 52W Low: ${ind.get('52w_low', 'N/A'):.2f}" if ind.get('52w_low') else "- 52W Low: N/A",
            "",
            "Evalúa el riesgo de esta inversión y determina precio de entrada, nivel de protección, precio objetivo y sizing óptimo.",
            "RECUERDA: NO uses bandas de score redondas (72, 65, 50…). Da scores PRECISOS con granularidad de 1-3 puntos basados en evidencia cuantitativa real. Cada análisis debe dar un score único que refleje sus particularidades.",
        ]

        return "\n".join(l for l in lines if l is not None)

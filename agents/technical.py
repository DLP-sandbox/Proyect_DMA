"""
Agente de Análisis Técnico — evalúa el setup técnico usando indicadores
clave, Stage Analysis de Minervini y detección de patrones VCP/breakout.
Retorna también los datos del chart para visualización en el dashboard.
"""
import anthropic
import pandas as pd

from agents.base import BaseAgent, AgentReport
from data.market_data import (
    get_price_history, get_weekly_history,
    compute_technical_indicators, get_relative_strength
)


SYSTEM_PROMPT = """Eres el analista técnico jefe de un hedge fund cuantitativo.
Tu análisis sigue el método de Mark Minervini (SEPA), Jesse Livermore y William O'Neil (CAN SLIM).

Evalúas:
1. STAGE ANALYSIS: Stage 2 (alcista, ideal para comprar) o no
2. TREND QUALITY: posición del precio respecto a MAs 50/150/200 diario y semanal
3. MOMENTUM: RSI, MACD, histograma — ¿hay momentum acelerado o desacelerando?
4. SETUP DE ENTRADA: ¿está en base tight? ¿hay patrón VCP, cup & handle, flat base?
5. VOLUMEN: confirmación de tendencia con OBV y volumen relativo
6. RELATIVE STRENGTH: ¿outperforma el S&P500 en 1M/3M/6M?
7. RIESGO DE ENTRADA: distancia al nivel de protección técnico (mínimo swing o MA 50W), R/R potencial

Criterios de scoring (escala continua 0-100, granular, sin clustering):
- 82-95: Stage 2 + bien posicionado vs MAs + RS fuerte + volumen confirmando. El score exacto depende de qué tan limpia esté la estructura.
- 67-81: Buen setup pero faltan confirmaciones (RS moderado, volumen débil, o cerca de resistencia).
- 53-66: Tendencia mixta, lateral, o sobrecomprada extrema (RSI >75).
- 38-52: Stage 3 en consolidación de empresa de calidad — bajo es TIMING no tesis rota.
- 20-37: Stage 3/4 con tendencia bajista clara y soportes rompiendo.
- <20: Breakdown técnico severo con volumen creciente a la baja.

REGLA ANTI-CLUSTERING: no uses 72, 65, 80 por defecto. Cada análisis debe tener score único que refleje sus particularidades (ej: 73 para Stage 2 con RS regular vs 78 para Stage 2 con RS fuerte y volumen alto).

IMPORTANTE: Una empresa de alta calidad estructural puede pasar meses en Stage 3 de consolidación natural sin que eso invalide la tesis de largo plazo. NO uses Stage 3/4 como descalificador automático — evalúa si hay deterioro real (RS deteriorándose, breakdown de soportes mayores, volumen distributivo) o si es solo consolidación lateral.

Retorna SIEMPRE este JSON exacto:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis técnico narrativo de 3 párrafos>",
  "pros": ["<señal alcista 1>", "<señal alcista 2>", "<señal alcista 3>"],
  "cons": ["<señal bajista 1>", "<señal bajista 2>"],
  "key_metrics": {
    "stage": "<Stage 1/2/3/4>",
    "rsi_14": "<valor>",
    "macd_signal": "<bullish|bearish|neutral>",
    "vs_sma50": "<+X%>",
    "vs_sma200": "<+X%>",
    "rs_vs_spy": "<+X% 6M>",
    "pct_from_52w_high": "<-X%>",
    "volume_trend": "<expanding|contracting>"
  },
  "sub_scores": {
    "trend_quality": <0-33>,
    "momentum": <0-33>,
    "setup_quality": <0-34>
  },
  "entry_setup": "<descripción del patrón técnico y punto ideal de entrada>",
  "key_levels": {
    "support": "<precio soporte clave>",
    "resistance": "<precio resistencia clave>",
    "stop_technical": "<nivel de protección técnico sugerido>"
  }
}
```"""


class TechnicalAgent(BaseAgent):
    name = "Técnico"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            # Daily data (2 años)
            df_daily = get_price_history(ticker, period="2y", interval="1d")
            # Weekly data (3 años para el weekly chart)
            df_weekly = get_weekly_history(ticker, period="3y")

            if df_daily.empty:
                return self._safe_report(ticker, "Sin datos de precio disponibles")

            # Indicadores diarios
            ind_daily = compute_technical_indicators(df_daily)
            # Indicadores semanales
            ind_weekly = compute_technical_indicators(df_weekly) if not df_weekly.empty else {}

            # Relative strength
            rs = get_relative_strength(ticker)

            user_message = self._build_message(ticker, df_daily, df_weekly, ind_daily, ind_weekly, rs)
            result = self._call_claude(SYSTEM_PROMPT, user_message)

            if "error" in result and "score" not in result:
                return self._safe_report(ticker, result.get("error", "Error desconocido"))

            sub_scores = result.get("sub_scores", {})
            snowflake_momentum = (sub_scores.get("trend_quality", 16) + sub_scores.get("momentum", 16)) / 2 / 33 * 20

            return AgentReport(
                agent_name=self.name,
                score=float(result.get("score", 50)),
                analysis=result.get("analysis", ""),
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                key_metrics=result.get("key_metrics", {}),
                conviction=result.get("conviction", "MEDIUM"),
                sub_scores={**sub_scores, "momentum_snowflake": snowflake_momentum},
                raw_data={
                    "daily_indicators":  ind_daily,
                    "weekly_indicators": ind_weekly,
                    "rs":                rs,
                    "key_levels":        result.get("key_levels", {}),
                    "entry_setup":       result.get("entry_setup", ""),
                    "df_daily":          df_daily.tail(252).to_dict() if not df_daily.empty else {},
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, df_daily, df_weekly, ind_d, ind_w, rs) -> str:
        price = ind_d.get("current_price", "N/A")
        lines = [
            f"# Análisis Técnico: {ticker}",
            f"**Precio actual:** ${price} | **Stage:** {ind_d.get('stage', 'N/A')}",
            "",
            "## Indicadores Diarios",
            f"- SMA 20: ${ind_d.get('sma_20', 'N/A'):.2f} | vs precio: {ind_d.get('price_vs_sma20_pct', 0):.1f}%" if ind_d.get('sma_20') else "- SMA 20: N/A",
            f"- SMA 50: ${ind_d.get('sma_50', 'N/A'):.2f} | vs precio: {ind_d.get('price_vs_sma50_pct', 0):.1f}%" if ind_d.get('sma_50') else "- SMA 50: N/A",
            f"- SMA 150: ${ind_d.get('sma_150', 'N/A'):.2f} | vs precio: {ind_d.get('price_vs_sma150_pct', 0):.1f}%" if ind_d.get('sma_150') else "- SMA 150: N/A",
            f"- SMA 200: ${ind_d.get('sma_200', 'N/A'):.2f} | vs precio: {ind_d.get('price_vs_sma200_pct', 0):.1f}%" if ind_d.get('sma_200') else "- SMA 200: N/A",
            f"- EMA 8: ${ind_d.get('ema_8', 'N/A'):.2f}" if ind_d.get('ema_8') else "- EMA 8: N/A",
            f"- EMA 21: ${ind_d.get('ema_21', 'N/A'):.2f}" if ind_d.get('ema_21') else "- EMA 21: N/A",
            "",
            "## Momentum",
            f"- RSI 14: {ind_d.get('rsi_14', 'N/A'):.1f}" if ind_d.get('rsi_14') else "- RSI 14: N/A",
            f"- MACD: {ind_d.get('macd', 0):.3f} | Signal: {ind_d.get('macd_signal', 0):.3f} | Hist: {ind_d.get('macd_hist', 0):.3f}" if ind_d.get('macd') else "- MACD: N/A",
            f"- BB Width: {ind_d.get('bb_width', 0):.1f}% (squeeze si < 5%)" if ind_d.get('bb_width') else "- BB Width: N/A",
            f"- OBV Trend: {ind_d.get('obv_trend', 'N/A')}",
            f"- Volumen relativo hoy: {ind_d.get('rel_volume', 1.0):.2f}x promedio 20d",
            f"- ATR 14: ${ind_d.get('atr_14', 0):.2f} ({ind_d.get('atr_pct', 0):.1f}% del precio)" if ind_d.get('atr_14') else "",
            "",
            "## Precio vs 52W",
            f"- 52W High: ${ind_d.get('52w_high', 'N/A'):.2f} | Distancia: {ind_d.get('pct_from_52w_high', 0):.1f}%",
            f"- 52W Low: ${ind_d.get('52w_low', 'N/A'):.2f} | Desde low: {ind_d.get('pct_from_52w_low', 0):.1f}%",
            "",
            "## Retornos",
            f"- 1 mes: {ind_d.get('return_1m', 'N/A'):.1f}%" if ind_d.get('return_1m') is not None else "- 1 mes: N/A",
            f"- 3 meses: {ind_d.get('return_3m', 'N/A'):.1f}%" if ind_d.get('return_3m') is not None else "- 3 meses: N/A",
            f"- 6 meses: {ind_d.get('return_6m', 'N/A'):.1f}%" if ind_d.get('return_6m') is not None else "- 6 meses: N/A",
            "",
            "## Relative Strength vs S&P500",
            f"- RS 1M: {rs.get('rs_1m', 'N/A'):.1f}%" if rs.get('rs_1m') is not None else "- RS 1M: N/A",
            f"- RS 3M: {rs.get('rs_3m', 'N/A'):.1f}%" if rs.get('rs_3m') is not None else "- RS 3M: N/A",
            f"- RS 6M: {rs.get('rs_6m', 'N/A'):.1f}%" if rs.get('rs_6m') is not None else "- RS 6M: N/A",
        ]

        # Weekly indicators
        if ind_w:
            lines += [
                "",
                "## Indicadores Semanales (más importantes para el trend)",
                f"- SMA 10W: ${ind_w.get('sma_20', 'N/A'):.2f}" if ind_w.get('sma_20') else "- SMA 10W: N/A",
                f"- SMA 30W: ${ind_w.get('sma_50', 'N/A'):.2f}" if ind_w.get('sma_50') else "- SMA 30W: N/A",
                f"- SMA 40W (200d): ${ind_w.get('sma_200', 'N/A'):.2f}" if ind_w.get('sma_200') else "- SMA 40W: N/A",
                f"- RSI Semanal: {ind_w.get('rsi_14', 'N/A'):.1f}" if ind_w.get('rsi_14') else "- RSI Semanal: N/A",
                f"- Stage Semanal: {ind_w.get('stage', 'N/A')}",
            ]

        lines += ["", "Realiza el análisis técnico completo y retorna el JSON especificado."]
        return "\n".join(l for l in lines if l is not None)

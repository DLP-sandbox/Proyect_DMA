"""
Agente de Análisis Fundamental — evalúa la calidad empresarial cuantitativa:
calidad, crecimiento, valoración, solidez financiera y potencial de DCF.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_company_info, get_financials, compute_quality_ratios, get_earnings_data


SYSTEM_PROMPT = """Eres el analista fundamental cuantitativo senior de un hedge fund de élite que ESPECIALIZA EN COMPOUNDERS DE CALIDAD A LARGO PLAZO.

Tu filosofía: la calidad estructural (moats, márgenes, ROIC) es lo que genera retornos sostenibles a 5-10 años. No subestimes la calidad por preocupaciones de valuación de corto plazo.

Debes analizar:
1. CALIDAD DEL NEGOCIO: márgenes brutos, operativos y netos; tendencia y sostenibilidad
2. CRECIMIENTO: revenue growth YoY, EPS growth, FCF growth, CAGR 2-3 años
3. RETORNO SOBRE CAPITAL: ROE, ROIC (>15% es excelente, >20% es excepcional, >25% es best-in-class)
4. SOLIDEZ FINANCIERA: deuda/equity, current ratio, FCF positivo y creciente
5. VALORACIÓN RELATIVA: P/E, P/S, EV/EBITDA, FCF yield vs sector y vs historia
6. CALIDAD DE EARNINGS: historial de beats/misses, consistencia de guidance
7. PIOTROSKI F-SCORE aproximado (0-9): señales de mejora en rentabilidad y apalancamiento

Retorna SIEMPRE este JSON exacto (sin markdown adicional fuera del bloque):
```json
{
  "score": <número 0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis CONCISO: 1-2 párrafos, máximo 6 líneas en total. Directo al grano, sin relleno ni repeticiones>",
  "pros": ["<pro 1>", "<pro 2>", "<pro 3>"],
  "cons": ["<con 1>", "<con 2>"],
  "key_metrics": {
    "revenue_growth": "<valor>",
    "gross_margin": "<valor>",
    "operating_margin": "<valor>",
    "fcf_yield": "<valor>",
    "roic": "<valor>",
    "debt_equity": "<valor>",
    "pe_ratio": "<valor>",
    "ev_ebitda": "<valor>"
  },
  "sub_scores": {
    "quality": <0-25>,
    "growth": <0-25>,
    "valuation": <0-25>,
    "financial_health": <0-25>
  },
  "dcf_thesis": "<potencial de valor intrínseco en 1 oración corta>",
  "earnings_quality": "<calidad y consistencia de earnings en 1 oración corta>"
}
```

Criterios de SCORING (escala 0-100, granular sin clustering):
Usa la escala continua, NO bandas redondas. Ajusta ±3 puntos según evidencia específica.

- 90-97: Best-in-class clarísimo — ROIC ≥25%, márgenes operativos ≥35%, moat ancho documentado, FCF creciente 15%+ YoY. Empresas excepcionales (Microsoft, Visa, ASML, Mastercard). El score exacto refleja qué tan extremas son las métricas.
- 80-89: Alta calidad sólida — ROIC 18-25%, márgenes 25-35%, FCF positivo creciente 8-15%, crecimiento sostenido.
- 68-79: Buena empresa por encima del promedio — ROIC 12-18%, márgenes 18-25%, crecimiento decente. El score exacto refleja la combinación específica.
- 55-67: Promedio del sector — métricas en línea con peers, sin clara ventaja diferencial.
- 40-54: Por debajo del promedio — márgenes bajos, ROIC 6-12%, crecimiento errático.
- 25-39: Pobre — ROIC <8%, deuda alta o márgenes negativos, crecimiento decreciente.
- <25: Negocio en deterioro estructural confirmado.

REGLA ANTI-CLUSTERING: dos empresas distintas NUNCA deben tener el mismo score. Calibra con precisión decimal aunque entregues entero (ej: 67, 71, 74, 78, no todos 72 ni todos 75).

IMPORTANTE: NO castigues valoración cara si la calidad lo justifica. Empresas best-in-class merecen premium. La valoración solo es problema si está claramente excesiva (P/E >40 sin justificación de crecimiento)."""


class FundamentalsAgent(BaseAgent):
    name = "Fundamentales"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            info = get_company_info(ticker)
            financials = get_financials(ticker)
            ratios = compute_quality_ratios(info, financials)
            earnings = get_earnings_data(ticker)

            user_message = self._build_message(ticker, info, financials, ratios, earnings)
            result = self._call_claude(SYSTEM_PROMPT, user_message)

            if "error" in result and "score" not in result:
                return self._safe_report(ticker, result["error"])

            sub_scores = result.get("sub_scores", {})
            snowflake = {
                "value":   sub_scores.get("valuation", 12) / 25 * 20,
                "quality": sub_scores.get("quality", 12) / 25 * 20,
                "growth":  sub_scores.get("growth", 12) / 25 * 20,
            }

            return AgentReport(
                agent_name=self.name,
                score=float(result.get("score", 50)),
                analysis=result.get("analysis", ""),
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                key_metrics=result.get("key_metrics", {}),
                conviction=result.get("conviction", "MEDIUM"),
                sub_scores={**sub_scores, **snowflake},
                raw_data={"ratios": ratios, "info_snippet": {
                    "pe": info.get("pe_ratio"),
                    "market_cap": info.get("market_cap"),
                    "sector": info.get("sector"),
                }},
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, financials, ratios, earnings) -> str:
        # Helpers para formateo seguro de valores YF
        def pct(v):
            return f"{v*100:.2f}%" if isinstance(v, (int, float)) else "N/A"
        def num(v, dec=2):
            return f"{v:.{dec}f}" if isinstance(v, (int, float)) else "N/A"
        def usd(v):
            if not isinstance(v, (int, float)) or v == 0:
                return "N/A"
            if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
            if abs(v) >= 1e9:  return f"${v/1e9:.2f}B"
            if abs(v) >= 1e6:  return f"${v/1e6:.0f}M"
            return f"${v:,.0f}"

        lines = [
            f"# Análisis Fundamental: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {info.get('sector')} | **Industria:** {info.get('industry')}",
            "",
            "⚠️ **INSTRUCCIÓN CRÍTICA DE FUENTE DE DATOS:**",
            "Los valores marcados con **[YF]** vienen DIRECTAMENTE de Yahoo Finance — son la fuente oficial.",
            "Cuando menciones cualquier métrica en tu análisis, usa LITERALMENTE los valores [YF].",
            "NO inventes, NO redondees agresivamente, NO uses datos de tu entrenamiento — solo los [YF] de abajo.",
            "",
            "## 📡 DATOS OFICIALES DE YAHOO FINANCE [YF]",
            f"- **Market Cap [YF]:** {usd(info.get('market_cap'))}",
            f"- **Revenue TTM [YF]:** {usd(info.get('revenue_ttm'))}",
            f"- **EBITDA [YF]:** {usd(info.get('ebitda_yf'))}",
            f"- **Free Cash Flow TTM [YF]:** {usd(info.get('fcf_yf'))}",
            f"- **Operating Cash Flow TTM [YF]:** {usd(info.get('ocf_yf'))}",
            f"- **Total Cash [YF]:** {usd(info.get('total_cash_yf'))}",
            f"- **Total Debt [YF]:** {usd(info.get('total_debt_yf'))}",
            f"- **Enterprise Value [YF]:** {usd(info.get('enterprise_value_yf'))}",
            "",
            "### Múltiplos de Valoración [YF]",
            f"- **P/E Trailing [YF]:** {num(info.get('pe_ratio'))}",
            f"- **P/E Forward [YF]:** {num(info.get('forward_pe'))}",
            f"- **P/S [YF]:** {num(info.get('ps_ratio'))}",
            f"- **P/B [YF]:** {num(info.get('pb_ratio'))}",
            f"- **EV/EBITDA [YF]:** {num(info.get('ev_ebitda'))}",
            f"- **EV/Revenue [YF]:** {num(info.get('ev_revenue_yf'))}",
            f"- **PEG Ratio [YF]:** {num(info.get('peg_ratio'))}",
            f"- **Beta [YF]:** {num(info.get('beta'))}",
            "",
            "### Márgenes [YF] (% reales — usa estos LITERALES)",
            f"- **Gross Margin [YF]:** {pct(info.get('gross_margin_yf'))}",
            f"- **Operating Margin [YF]:** {pct(info.get('operating_margin_yf'))}",
            f"- **Profit Margin (Net) [YF]:** {pct(info.get('profit_margin'))}",
            "",
            "### Rentabilidad [YF]",
            f"- **ROE [YF]:** {pct(info.get('roe_yf'))}",
            f"- **ROA [YF]:** {pct(info.get('roa_yf'))}",
            f"- **ROIC (calculado):** {num(ratios.get('roic'), 1) + '%' if ratios.get('roic') is not None else 'N/A'}",
            "",
            "### Crecimiento [YF]",
            f"- **Revenue Growth YoY [YF]:** {pct(info.get('revenue_growth_yf'))}",
            f"- **Earnings Growth YoY [YF]:** {pct(info.get('earnings_growth_yf'))}",
            "",
            "### Solidez Financiera [YF]",
            f"- **Debt/Equity [YF]:** {num(info.get('debt_equity_yf'))} (tal cual lo muestra Yahoo Finance)",
            f"- **Current Ratio [YF]:** {num(info.get('current_ratio_yf'))}",
            f"- **Quick Ratio [YF]:** {num(info.get('quick_ratio_yf'))}",
            "",
            "### Precio y Analistas [YF]",
            f"- **Precio actual [YF]:** ${num(info.get('current_price'))}",
            f"- **52w High/Low [YF]:** ${num(info.get('52w_high'))} / ${num(info.get('52w_low'))}",
            f"- **Target Mean Analistas [YF]:** ${num(info.get('target_price'))}",
            f"- **Target High/Low [YF]:** ${num(info.get('target_high_yf'))} / ${num(info.get('target_low_yf'))}",
            f"- **Número de analistas [YF]:** {info.get('num_analysts_yf', 'N/A')}",
            f"- **Recomendación analistas [YF]:** {info.get('analyst_rating', 'N/A')}",
            f"- **Dividend Yield [YF]:** {pct(info.get('dividend_yield'))}",
            "",
            "## 📊 Métricas Calculadas (complemento)",
            f"- Revenue CAGR 2Y: {ratios.get('revenue_cagr_2y', 'N/A'):.1f}%" if isinstance(ratios.get('revenue_cagr_2y'), (int, float)) else "- Revenue CAGR 2Y: N/A",
            f"- FCF Yield: {ratios.get('fcf_yield', 'N/A'):.2f}%" if isinstance(ratios.get('fcf_yield'), (int, float)) else "- FCF Yield: N/A",
            f"- FCF Growth YoY: {ratios.get('fcf_growth_yoy', 'N/A'):.1f}%" if isinstance(ratios.get('fcf_growth_yoy'), (int, float)) else "- FCF Growth YoY: N/A",
        ]

        # Revenue history
        rev = financials.get("revenue", [])
        years = financials.get("fiscal_years", [])
        if rev and years:
            lines.append("")
            lines.append("## Revenue Histórico")
            for y, r in zip(years, rev):
                if r:
                    lines.append(f"- {y}: ${r / 1e9:.2f}B")

        # FCF history
        fcf = financials.get("free_cash_flow", [])
        if fcf:
            lines.append("")
            lines.append("## Free Cash Flow Histórico")
            for y, f in zip(years, fcf):
                if f:
                    lines.append(f"- {y}: ${f / 1e6:.0f}M")

        # Earnings history
        eh = earnings.get("earnings_history", [])
        if eh:
            lines.append("")
            lines.append(f"## Historial Earnings (últimos {len(eh)} quarters)")
            lines.append(f"- Promedio surprise: {earnings.get('avg_surprise', 0):.1f}%")
            lines.append(f"- Beats consecutivos: {earnings.get('beat_count', 0)}/{len(eh)}")
            lines.append(f"- Próximos earnings: {earnings.get('next_earnings', 'N/A')}")
            for e in eh[:4]:
                lines.append(f"  • {e['date']}: Est ${e['estimate']:.2f} → Act ${e['actual']:.2f} ({'+' if e['surprise_pct'] > 0 else ''}{e['surprise_pct']:.1f}%)")

        lines.append("")
        lines.append("Realiza el análisis fundamental completo y retorna el JSON especificado.")

        return "\n".join(l for l in lines if l is not None)

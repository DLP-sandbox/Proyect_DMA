"""
Agente Macro & Rotación Sectorial — evalúa el contexto macro para
determinar si el viento está a favor o en contra de la acción.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_macro_data, get_company_info


SYSTEM_PROMPT = """Eres el macro strategist de un hedge fund, con el pensamiento de Stanley Druckenmiller y Ray Dalio combinados.

Tu trabajo es determinar si el entorno macro es favorable o adverso para esta acción específica en este momento.

Analizas:
1. ENTORNO DE TASAS: Fed policy, yield curve, correlación de la acción con tasas
2. ROTACIÓN SECTORIAL: ¿El sector de esta acción está en momentum positivo o negativo vs el mercado?
3. RISK-ON / RISK-OFF: ¿VIX, crédito y dólar señalan apetito de riesgo o huida hacia activos seguros?
4. MACRO HEADWINDS/TAILWINDS: Crecimiento económico, inflación, empleo — ¿favorecen este tipo de negocio?
5. LIQUIDEZ DEL MERCADO: ¿El mercado en general está en modo expansión o contracción?
6. ALINEACIÓN SECTOR: ¿El sector de la empresa está rotando hacia arriba en el mercado?

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis macro en 2-3 párrafos>",
  "pros": ["<viento de cola macro 1>", "<viento de cola macro 2>"],
  "cons": ["<viento en contra macro 1>", "<viento en contra macro 2>"],
  "key_metrics": {
    "market_environment": "<risk-on|neutral|risk-off>",
    "rate_sensitivity": "<high positive|low|high negative>",
    "sector_momentum": "<strong|neutral|weak>",
    "vix_level": "<low <20|elevated 20-30|high >30>",
    "yield_curve": "<normal|flat|inverted>",
    "dollar_impact": "<favorable|neutral|unfavorable>"
  },
  "sub_scores": {
    "macro_environment": <0-34>,
    "sector_rotation": <0-33>,
    "liquidity_conditions": <0-33>
  },
  "macro_verdict": "<en 1-2 oraciones: el macro es viento de cola, neutro o viento en contra para esta acción>"
}
```"""


class MacroAgent(BaseAgent):
    name = "Macro & Sector"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            macro = get_macro_data()
            info = get_company_info(ticker)

            user_message = self._build_message(ticker, info, macro)
            result = self._call_claude(SYSTEM_PROMPT, user_message)

            if "error" in result and "score" not in result:
                return self._safe_report(ticker, result.get("error", "Error"))

            return AgentReport(
                agent_name=self.name,
                score=float(result.get("score", 50)),
                analysis=result.get("analysis", ""),
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                key_metrics=result.get("key_metrics", {}),
                conviction=result.get("conviction", "MEDIUM"),
                sub_scores=result.get("sub_scores", {}),
                raw_data={
                    "macro_verdict": result.get("macro_verdict", ""),
                    "sector": info.get("sector"),
                    "macro_snapshot": macro,
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, macro) -> str:
        sector = info.get("sector", "Unknown")

        def fmt_change(d, key):
            val = d.get(key, {})
            if isinstance(val, dict):
                curr = val.get("current", "N/A")
                chg1m = val.get("1m_change")
                chg3m = val.get("3m_change")
                parts = [f"${curr:.2f}" if isinstance(curr, float) else str(curr)]
                if chg1m is not None:
                    parts.append(f"1M: {'+' if chg1m > 0 else ''}{chg1m:.1f}%")
                if chg3m is not None:
                    parts.append(f"3M: {'+' if chg3m > 0 else ''}{chg3m:.1f}%")
                return " | ".join(parts)
            return str(val)

        lines = [
            f"# Análisis Macro & Sector: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {sector} | **Beta:** {info.get('beta', 1.0):.2f}",
            "",
            "## Indicadores de Mercado Actuales (índices reales, no ETFs)",
            f"- S&P 500 Index (^GSPC): {fmt_change(macro, 'sp500')}",
            f"- NASDAQ Composite (^IXIC): {fmt_change(macro, 'nasdaq')}",
            f"- VIX (Fear Index): {fmt_change(macro, 'vix')}",
            f"- DXY (US Dollar Index): {fmt_change(macro, 'dxy')}",
            f"- 10Y Treasury Yield: {fmt_change(macro, 'tnx')}%",
            f"- 30Y Treasury Yield: {fmt_change(macro, 'tyx')}%",
            f"- Yield Curve (10Y-2Y): {macro.get('yield_curve_spread', 'N/A'):.2f}%" if isinstance(macro.get('yield_curve_spread'), float) else f"- Yield Curve: N/A",
            f"- Gold: {fmt_change(macro, 'gold')}",
            f"- Oil (WTI): {fmt_change(macro, 'oil')}",
            "",
            "## Rotación Sectorial (rendimiento 1 mes)",
        ]

        sector_perf = macro.get("sector_performance", {})
        if sector_perf:
            sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
            for s_name, ret in sorted_sectors:
                marker = " ← SECTOR DE LA EMPRESA" if sector and s_name.lower() in sector.lower() else ""
                sign = "+" if ret > 0 else ""
                lines.append(f"- {s_name}: {sign}{ret:.1f}%{marker}")

        lines += [
            "",
            f"**Beta de la acción:** {info.get('beta', 1.0):.2f} (sensibilidad al mercado)",
            "",
            "Evalúa si el entorno macro es favorable para esta acción específica y retorna el JSON.",
        ]

        return "\n".join(l for l in lines if l is not None)

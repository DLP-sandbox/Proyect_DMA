"""
Agente de Flujo Institucional & Smart Money — detecta movimientos de dinero
inteligente: cambios en ownership institucional, insider buying/selling,
short interest y posicionamiento de grandes fondos.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_holders_data, get_company_info


SYSTEM_PROMPT = """Eres el especialista en flujo institucional de un hedge fund. Tu trabajo es leer las señales del "smart money":
quién está comprando, quién está vendiendo, y qué significa eso para el precio futuro.

Interpretas:
1. INSIDER BUYING: Cuando insiders compran (especialmente CEO/CFO/directors) con dinero real, es una señal muy alcista. El insider selling es casi siempre neutral (liquidez personal), pero el buying es una apuesta con convicción.
2. PROPIEDAD INSTITUCIONAL: Alta concentración institucional + nuevas entradas de fondos de calidad = validación. Demasiada concentración = riesgo de crowded trade.
3. SHORT INTEREST: Short interest alto (>15% float) + mejora fundamental = potencial squeeze. Bajo short interest = institucionales no están apostando en contra.
4. CALIDAD DE LOS INSTITUCIONALES: ¿Están los mejores fondos (Fidelity, Vanguard, Tiger Global, Coatue)? ¿O son solo ETFs pasivos?

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis de flujo institucional en 2-3 párrafos>",
  "pros": ["<señal positiva 1>", "<señal positiva 2>"],
  "cons": ["<señal negativa 1>", "<señal negativa 2>"],
  "key_metrics": {
    "institutional_ownership": "<X%>",
    "insider_buying_signal": "<bullish|neutral|bearish>",
    "short_interest": "<X% del float>",
    "squeeze_potential": "<low|medium|high>",
    "smart_money_signal": "<accumulating|neutral|distributing>"
  },
  "sub_scores": {
    "insider_signal": <0-33>,
    "institutional_quality": <0-33>,
    "short_interest_dynamic": <0-34>
  },
  "key_insight": "<la señal más importante de flujo institucional en 1-2 oraciones>"
}
```"""


class InstitutionalAgent(BaseAgent):
    name = "Smart Money"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            holders = get_holders_data(ticker)
            info = get_company_info(ticker)

            user_message = self._build_message(ticker, info, holders)
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
                    "key_insight": result.get("key_insight", ""),
                    "holders_raw": holders,
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, holders) -> str:
        lines = [
            f"# Análisis de Flujo Institucional: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {info.get('sector')} | **Market Cap:** ${info.get('market_cap', 0) / 1e9:.1f}B",
            f"**Short Ratio (days to cover):** {info.get('short_ratio', 'N/A')}",
            f"**Short % del Float:** {(info.get('short_percent', 0) or 0) * 100:.1f}%",
            f"**Float Shares:** {info.get('float_shares', 0) / 1e6:.1f}M" if info.get('float_shares') else "**Float Shares:** N/A",
            "",
        ]

        # Top institucionales
        top_inst = holders.get("top_institutions", [])
        if top_inst:
            lines.append("## Top Tenedores Institucionales")
            for inst in top_inst[:8]:
                holder = inst.get("Holder", inst.get("holder", "Unknown"))
                pct = inst.get("% Out", inst.get("pctHeld", 0))
                shares = inst.get("Shares", inst.get("shares", 0))
                val = inst.get("Value", inst.get("value", 0))
                if isinstance(pct, float):
                    lines.append(f"- **{holder}**: {pct:.2%} del outstanding | {shares:,.0f} shares | ${val / 1e6:.0f}M" if isinstance(shares, (int, float)) else f"- **{holder}**: {pct:.2%}")
                else:
                    lines.append(f"- **{holder}**: {pct}")
            lines.append(f"\n**Total Institutional Ownership:** {holders.get('institutional_ownership_pct', 'N/A')}")

        lines.append("")

        # Insider transactions
        insider_buys = holders.get("recent_insider_buys", 0)
        insider_txns = holders.get("insider_transactions", [])

        lines.append(f"## Transacciones de Insiders (últimas 20)")
        lines.append(f"**Compras recientes de insiders:** {insider_buys}")

        if insider_txns:
            for txn in insider_txns[:10]:
                date = str(txn.get("Date", ""))[:10]
                insider = txn.get("Insider", "Unknown")
                pos = txn.get("Position", "")
                shares = txn.get("Shares", 0)
                val = txn.get("Value", 0)
                lines.append(f"- {date} | {insider} ({pos}): {shares:,} shares | ${val:,.0f}")

        lines += [
            "",
            "Analiza las señales de flujo institucional y retorna el JSON especificado.",
            "Si los datos de holders son limitados, indícalo pero igual da un score basado en lo disponible.",
        ]

        return "\n".join(l for l in lines if l is not None)

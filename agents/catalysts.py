"""
Agente de Catalizadores — identifica eventos cercanos que pueden mover
el precio: earnings, FDA, contratos, lanzamientos, revisiones de analistas.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_earnings_data, get_news, get_company_info


SYSTEM_PROMPT = """Eres el analista de eventos y catalizadores de un hedge fund de élite.
Tu trabajo es identificar los catalizadores concretos que pueden hacer que el precio se mueva +20% o más en los próximos 3-12 meses.

⏱ CONTEXTO TEMPORAL: Recibirás un header con la fecha actual EXACTA. USA esa fecha para calcular cuántos días faltan para cada earnings/evento, y prioriza los catalizadores más próximos. Si una noticia es antigua (>30 días), su impacto ya está descontado.

Analizas:
1. EARNINGS NEXT QUARTER: ¿Hay earnings próximos? ¿Historial de beats? ¿Setup de sorpresa positiva?
2. REVISIONES DE ANALISTAS: ¿Están subiendo targets y ratings? Momentum de revisiones = señal potente
3. CATALIZADORES ESPECÍFICOS: Lanzamientos de productos, FDA approvals, contratos gubernamentales, spin-offs, M&A, recompras masivas
4. EARNINGS REVISION MOMENTUM: El factor estadísticamente más potente. ¿Las estimaciones de consenso están subiendo?
5. EVENTOS DE RIESGO: ¿Hay riesgo regulatorio, juicios, investigaciones, pérdida de clientes clave?
6. TIMING: ¿Cuándo ocurren estos catalizadores? ¿En los próximos 30, 90 o 180 días?

Scoring (escala continua 0-100, granular, sin clustering):
- 83-95: Múltiples catalizadores positivos claros con timing definido (<60 días) + historial fuerte de ejecución.
- 68-82: Catalizadores reales pero con incertidumbre de timing o magnitud.
- 53-67: Mixtos — algunos positivos compensados por riesgos de evento.
- 35-52: Catalizadores lejanos (>180 días) o débiles, riesgo de evento real.
- 18-34: Sin catalizadores claros y/o riesgos de evento materiales.
- <18: Riesgo de catalizador NEGATIVO inminente (juicio, regulación, downgrade masivo).

REGLA ANTI-CLUSTERING: cada análisis tiene un perfil único de catalizadores. No uses 28, 50, 72 por defecto. Calibra al detalle (ej: 56 vs 61 dependiendo de proximidad de earnings).

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis de catalizadores CONCISO: 1-2 párrafos, máximo 5 líneas en total. Directo al grano, sin relleno>",
  "pros": ["<catalizador positivo 1>", "<catalizador positivo 2>"],
  "cons": ["<riesgo de evento 1>", "<riesgo de evento 2>"],
  "key_metrics": {
    "next_earnings": "<fecha o N/A>",
    "earnings_beat_rate": "<X/Y últimos quarters>",
    "avg_earnings_surprise": "<+X%>",
    "analyst_sentiment_trend": "<improving|stable|deteriorating>",
    "catalyst_timeline": "<30d|90d|180d|>180d>",
    "key_upcoming_event": "<descripción del catalizador más importante>"
  },
  "sub_scores": {
    "earnings_momentum": <0-34>,
    "catalyst_quality": <0-33>,
    "analyst_revision_trend": <0-33>
  },
  "top_catalyst": "<el catalizador #1 que podría mover el precio, en 1 oración corta>"
}
```"""


class CatalystsAgent(BaseAgent):
    name = "Catalizadores"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            earnings = get_earnings_data(ticker)
            news = get_news(ticker, max_items=15)
            info = get_company_info(ticker)

            user_message = self._build_message(ticker, info, earnings, news)
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
                    "top_catalyst": result.get("top_catalyst", ""),
                    "next_earnings": earnings.get("next_earnings"),
                    "beat_count": earnings.get("beat_count", 0),
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, earnings, news) -> str:
        lines = [
            f"# Análisis de Catalizadores: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {info.get('sector')} | **Industria:** {info.get('industry')}",
            f"**Analyst Rating (consenso):** {info.get('analyst_rating', 'N/A')}",
            f"**Target Price Consenso:** ${info.get('target_price', 'N/A')}",
            f"**Precio Actual:** ${info.get('current_price', 'N/A')}",
            "",
            "## Datos de Earnings (calculado desde HOY)",
            f"- Próximos Earnings: **{earnings.get('next_earnings', 'N/A')}** "
            f"({earnings.get('days_to_next_earnings', 'N/A')} días desde hoy) "
            f"{earnings.get('next_earnings_proximity', '')}",
            f"- Beats en últimos quarters: {earnings.get('beat_count', 'N/A')}",
            f"- Surprise promedio: {earnings.get('avg_surprise', 0):.1f}%" if earnings.get('avg_surprise') is not None else "- Surprise promedio: N/A",
            "",
        ]

        # Historial detallado de earnings
        eh = earnings.get("earnings_history", [])
        if eh:
            lines.append("## Historial Earnings Reciente")
            for e in eh[:6]:
                sign = "+" if e["surprise_pct"] > 0 else ""
                lines.append(f"- {e['date']}: Est ${e['estimate']:.2f} → Act ${e['actual']:.2f} ({sign}{e['surprise_pct']:.1f}%)")

        # Noticias categorizadas con freshness
        if news:
            lines.append("")
            lines.append("## Noticias y Eventos Recientes (ordenados de más reciente a más antiguo)")
            for item in news:
                freshness = item.get("freshness", "")
                age = item.get("age_hours", 0)
                age_label = f"{age:.0f}h ago" if age < 48 else f"{age/24:.0f}d ago"
                lines.append(f"- {freshness} [{age_label}] **{item.get('publisher', '')}**: {item.get('title', '')}")

        lines += [
            "",
            "## Contexto de Sector",
            f"- Sector: {info.get('sector')}",
            f"- Industria: {info.get('industry')}",
            "",
            "Identifica los catalizadores clave y retorna el JSON especificado.",
            "Busca especialmente señales de earnings revision momentum y catalizadores asimétricos.",
        ]

        return "\n".join(l for l in lines if l is not None)

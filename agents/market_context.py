"""
Agente combinado de Contexto de Mercado — fusiona Macro + Sentimiento +
Catalizadores en UNA sola llamada a la IA para optimizar costos (~3 llamadas → 1).

CLAVE: devuelve 3 AgentReport separados ("macro", "sentiment", "catalysts")
con EXACTAMENTE la misma estructura que los 3 agentes originales, para que el
orquestador (scoring, weights, breakdown) y el dashboard (gráficas, tiles,
gauges) sigan funcionando SIN ningún cambio downstream. Lo único que cambia es
que estos 3 reportes se generan con 1 llamada en vez de 3.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import (
    get_macro_data, get_news, get_earnings_data, get_company_info,
)
from data.events import get_catalyst_events


SYSTEM_PROMPT = """Eres el estratega de contexto de mercado de un hedge fund de élite. Cubres TRES dominios en un solo análisis integrado: (1) MACRO & rotación sectorial, (2) SENTIMIENTO & narrativa, (3) CATALIZADORES & eventos.

⏱ CONTEXTO TEMPORAL: Recibirás la fecha actual EXACTA. Úsala para calcular días hasta earnings/eventos y para evaluar qué tan reciente es cada noticia.

Para cada dominio, evalúa con rigor:

MACRO: ¿El entorno de tasas, VIX, dólar y rotación sectorial es viento de cola o en contra para esta acción? ¿El sector está rotando hacia arriba?

SENTIMIENTO: ¿La narrativa mediática mejora o se deteriora? ¿Hay divergencia sentimiento-fundamentales (oportunidad)? ¿Sentimiento extremo = señal contraria? ¿Riesgo reputacional/ESG?

CATALIZADORES: NO te limites a los earnings. Recibirás una AGENDA DE EVENTOS PRÓXIMOS (conferencias y lanzamientos de producto tipo WWDC/GTC/re:Invent, ex-dividendos, juntas de accionistas, rebalanceos de índice, entregas trimestrales) y los HECHOS RELEVANTES RECIENTES que la empresa ha comunicado oficialmente a la SEC (contratos materiales firmados, compras o ventas de activos, cambios en la directiva, reestructuraciones). Úsalos:
- Cada pro y cada con debe estar ANCLADO a un evento concreto con su fecha o su plazo en días ("Keynote del 14-sep a 47 días…"), nunca a una generalidad.
- Un evento marcado como ~aprox es una ESTIMACIÓN por recurrencia anual: menciónalo como ventana aproximada, JAMÁS como fecha confirmada.
- Pondera por proximidad e impacto: un lanzamiento a 30 días pesa más que una feria a 200.
- Un contrato material reciente o un cambio de CEO son catalizadores de primer orden aunque no haya earnings cerca.
¿Hay además revisiones de analistas subiendo? ¿Riesgos de evento (litigios, regulación, dilución)?

Scoring: escala continua 0-100, granular, SIN clustering (no uses 28/50/72 por defecto; calibra al detalle).

Retorna SIEMPRE este JSON con las TRES secciones:
```json
{
  "macro": {
    "score": <0-100>,
    "conviction": "<HIGH|MEDIUM|LOW>",
    "analysis": "<análisis macro CONCISO: máximo 4 líneas. Directo, sin relleno>",
    "pros": ["<las 3 vientos de cola macro MÁS importantes>"],
    "cons": ["<los 3 vientos en contra macro MÁS importantes>"],
    "key_metrics": {
      "market_environment": "<risk-on|neutral|risk-off>",
      "rate_sensitivity": "<high positive|low|high negative>",
      "sector_momentum": "<strong|neutral|weak>",
      "vix_level": "<low <20|elevated 20-30|high >30>",
      "yield_curve": "<normal|flat|inverted>",
      "dollar_impact": "<favorable|neutral|unfavorable>"
    },
    "sub_scores": {"macro_environment": <0-34>, "sector_rotation": <0-33>, "liquidity_conditions": <0-33>},
    "macro_verdict": "<en 1 oración: el macro es viento de cola, neutro o en contra>"
  },
  "sentiment": {
    "score": <0-100>,
    "conviction": "<HIGH|MEDIUM|LOW>",
    "analysis": "<análisis de sentimiento CONCISO: máximo 4 líneas. Directo, sin relleno>",
    "pros": ["<las 3 señales positivas de sentimiento MÁS importantes>"],
    "cons": ["<los 3 riesgos de narrativa MÁS importantes>"],
    "key_metrics": {
      "overall_sentiment": "<very bullish|bullish|neutral|bearish|very bearish>",
      "sentiment_momentum": "<improving|stable|deteriorating>",
      "narrative_theme": "<crecimiento|turnaround|defensivo|disrupción|especulativo>",
      "contrarian_signal": "<buy the fear|no signal|sell the hype>",
      "reputational_risk": "<low|medium|high>"
    },
    "sub_scores": {"news_sentiment": <0-34>, "narrative_momentum": <0-33>, "contrarian_value": <0-33>},
    "dominant_narrative": "<la narrativa dominante en 1-2 oraciones>",
    "opportunity": "<si hay divergencia sentimiento-fundamentales descríbela; si no, 'No hay divergencia clara'>"
  },
  "catalysts": {
    "score": <0-100>,
    "conviction": "<HIGH|MEDIUM|LOW>",
    "analysis": "<análisis de catalizadores CONCISO: máximo 4 líneas. Directo, sin relleno>",
    "pros": ["<los 3 catalizadores positivos MÁS importantes>"],
    "cons": ["<los 3 riesgos de evento MÁS importantes>"],
    "key_metrics": {
      "next_earnings": "<fecha o N/A>",
      "earnings_beat_rate": "<X/Y últimos quarters>",
      "avg_earnings_surprise": "<+X%>",
      "analyst_sentiment_trend": "<improving|stable|deteriorating>",
      "catalyst_timeline": "<30d|90d|180d|>180d>",
      "key_upcoming_event": "<el catalizador más importante>"
    },
    "sub_scores": {"earnings_momentum": <0-34>, "catalyst_quality": <0-33>, "analyst_revision_trend": <0-33>},
    "top_catalyst": "<el catalizador #1 que podría mover el precio, en 1 oración corta>",
    "upcoming_events": [
      {"fecha": "<YYYY-MM-DD o 'próximas semanas'>", "evento": "<qué ocurre, breve>", "impacto": "<alto|medio|bajo>", "direccion": "<alcista|bajista|incierto>"}
    ]
  }
}
```

`upcoming_events`: MÁXIMO 5. Solo eventos futuros RELEVANTES que hayas detectado en las NOTICIAS y que NO estén ya en la agenda que te pasan (esa ya se muestra aparte). Si no encuentras ninguno, devuelve una lista vacía — no rellenes con lo que ya está en la agenda ni inventes fechas.

REGLA: máximo 3 pros y 3 cons por sección — solo los MÁS importantes. Mantén los valores cortos de key_metrics EXACTAMENTE en su forma especificada (el dashboard depende de ellos)."""


class MarketContextAgent(BaseAgent):
    name = "Contexto de Mercado"

    def analyze(self, ticker: str, data: dict = None) -> dict:
        """Retorna un DICT de 3 AgentReport: {"macro":, "sentiment":, "catalysts":}.
        El orquestador detecta el dict y los fusiona en reports[...]."""
        try:
            macro = get_macro_data()
            news = get_news(ticker, max_items=15)
            earnings = get_earnings_data(ticker)
            info = get_company_info(ticker)
            # Agenda de eventos + hechos relevantes de la SEC. Tiene su propia
            # capa determinista y sus respaldos; NUNCA lanza y en el peor caso
            # devuelve la estructura vacía, así que no puede tumbar el análisis.
            eventos = get_catalyst_events(ticker, info, earnings)

            user_message = self._build_message(ticker, info, macro, news, earnings, eventos)
            # Más tokens que un agente normal porque genera 3 secciones en una
            # sola respuesta JSON. 3800 evitaba que se truncara (era el bug: con
            # 2000 el JSON quedaba incompleto y no parseaba); con la agenda de
            # eventos y `upcoming_events` el JSON crece, así que sube a 4600.
            result = self._call_claude(SYSTEM_PROMPT, user_message, max_tokens=4600)

            # Si la llamada falló completamente, devolver 3 safe reports
            if "error" in result and "macro" not in result and "score" not in result:
                err = result.get("error", "Error")
                return {
                    "macro":     self._safe_section("Macro & Sector", err),
                    "sentiment": self._safe_section("Sentimiento", err),
                    "catalysts": self._safe_section("Catalizadores", err),
                }

            m = result.get("macro", {}) or {}
            s = result.get("sentiment", {}) or {}
            c = result.get("catalysts", {}) or {}

            # ── MACRO report (estructura idéntica a MacroAgent) ──
            macro_report = AgentReport(
                agent_name="Macro & Sector",
                score=float(m.get("score", 50)),
                analysis=m.get("analysis", ""),
                pros=list(m.get("pros", []))[:3],
                cons=list(m.get("cons", []))[:3],
                key_metrics=m.get("key_metrics", {}),
                conviction=m.get("conviction", "MEDIUM"),
                sub_scores=m.get("sub_scores", {}),
                raw_data={
                    "macro_verdict": m.get("macro_verdict", ""),
                    "sector": info.get("sector"),
                    "macro_snapshot": macro,
                },
            )

            # ── SENTIMENT report (estructura idéntica a SentimentAgent) ──
            sentiment_report = AgentReport(
                agent_name="Sentimiento",
                score=float(s.get("score", 50)),
                analysis=s.get("analysis", ""),
                pros=list(s.get("pros", []))[:3],
                cons=list(s.get("cons", []))[:3],
                key_metrics=s.get("key_metrics", {}),
                conviction=s.get("conviction", "MEDIUM"),
                sub_scores=s.get("sub_scores", {}),
                raw_data={
                    "dominant_narrative": s.get("dominant_narrative", ""),
                    "opportunity": s.get("opportunity", ""),
                    "news_count": len(news),
                },
            )

            # ── CATALYSTS report (estructura idéntica a CatalystsAgent) ──
            catalysts_report = AgentReport(
                agent_name="Catalizadores",
                score=float(c.get("score", 50)),
                analysis=c.get("analysis", ""),
                pros=list(c.get("pros", []))[:3],
                cons=list(c.get("cons", []))[:3],
                key_metrics=c.get("key_metrics", {}),
                conviction=c.get("conviction", "MEDIUM"),
                sub_scores=c.get("sub_scores", {}),
                raw_data={
                    "top_catalyst": c.get("top_catalyst", ""),
                    "next_earnings": earnings.get("next_earnings"),
                    "beat_count": earnings.get("beat_count", 0),
                    # Se guardan con el análisis (raw_data ya persiste a disco y
                    # a la nube), así que un análisis reabierto del historial
                    # conserva su agenda aunque las fuentes estén caídas.
                    "agenda": (eventos or {}).get("agenda", []),
                    "hechos_recientes": (eventos or {}).get("hechos_recientes", []),
                    "upcoming_events": list(c.get("upcoming_events", []) or [])[:5],
                },
            )

            return {
                "macro": macro_report,
                "sentiment": sentiment_report,
                "catalysts": catalysts_report,
            }
        except Exception as e:
            err = str(e)
            return {
                "macro":     self._safe_section("Macro & Sector", err),
                "sentiment": self._safe_section("Sentimiento", err),
                "catalysts": self._safe_section("Catalizadores", err),
            }

    def _safe_section(self, agent_name: str, error: str) -> AgentReport:
        """Reporte seguro para una sección si la combinada falla."""
        return AgentReport(
            agent_name=agent_name,
            score=50,
            analysis=("No pudimos completar esta parte del análisis en este momento. "
                      "Intenta de nuevo en un rato."),
            pros=[],
            cons=["Datos insuficientes por ahora"],
            conviction="LOW",
            error=error,
        )

    def _build_message(self, ticker, info, macro, news, earnings, eventos=None) -> str:
        sector = info.get("sector", "Unknown")

        def fmt_change(d, key):
            val = d.get(key, {})
            if isinstance(val, dict):
                curr = val.get("current", "N/A")
                chg1m = val.get("1m_change")
                parts = [f"${curr:.2f}" if isinstance(curr, float) else str(curr)]
                if chg1m is not None:
                    parts.append(f"1M: {'+' if chg1m > 0 else ''}{chg1m:.1f}%")
                return " | ".join(parts)
            return str(val)

        lines = [
            f"# Contexto de Mercado: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {sector} | **Industria:** {info.get('industry')} | "
            # OJO: `.get(clave, defecto)` solo aplica el defecto si la clave NO
            # existe. get_company_info SÍ devuelve la clave con valor None (KO,
            # por ejemplo, no trae beta), y entonces `None:.2f` lanzaba
            # TypeError y este agente combinado moría entero — dejando SIN
            # análisis a macro, sentimiento Y catalizadores a la vez. El `or`
            # (idioma ya usado en el resto de agentes) lo blinda.
            f"**Beta:** {(info.get('beta') or 1.0):.2f} | "
            f"**Market Cap:** ${(info.get('market_cap') or 0) / 1e9:.1f}B",
            f"**Analyst Rating:** {info.get('analyst_rating', 'N/A')} | "
            f"**Target:** ${info.get('target_price', 'N/A')} vs Actual ${info.get('current_price', 'N/A')}",
            "",
            "## 1) MACRO — Indicadores de Mercado",
            f"- S&P 500: {fmt_change(macro, 'sp500')}",
            f"- NASDAQ: {fmt_change(macro, 'nasdaq')}",
            f"- VIX: {fmt_change(macro, 'vix')}",
            f"- DXY (Dólar): {fmt_change(macro, 'dxy')}",
            f"- 10Y Treasury: {fmt_change(macro, 'tnx')}%",
            f"- Gold: {fmt_change(macro, 'gold')} | Oil: {fmt_change(macro, 'oil')}",
        ]

        sector_perf = macro.get("sector_performance", {})
        if sector_perf:
            lines.append("### Rotación Sectorial (1M):")
            sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
            for s_name, ret in sorted_sectors:
                marker = " ← SECTOR DE LA EMPRESA" if sector and s_name.lower() in sector.lower() else ""
                sign = "+" if ret > 0 else ""
                lines.append(f"- {s_name}: {sign}{ret:.1f}%{marker}")

        # ── Earnings (para catalizadores) ──
        lines += [
            "",
            "## 2) CATALIZADORES — Earnings & Eventos (calculado desde HOY)",
            f"- Próximos Earnings: **{earnings.get('next_earnings', 'N/A')}** "
            f"({earnings.get('days_to_next_earnings', 'N/A')} días) "
            f"{earnings.get('next_earnings_proximity', '')}",
            f"- Beats recientes: {earnings.get('beat_count', 'N/A')} | "
            f"Surprise promedio: {earnings.get('avg_surprise', 0):.1f}%"
            if earnings.get('avg_surprise') is not None else
            f"- Beats recientes: {earnings.get('beat_count', 'N/A')} | Surprise promedio: N/A",
        ]
        eh = earnings.get("earnings_history", [])
        if eh:
            lines.append("### Historial Earnings:")
            for e in eh[:5]:
                sign = "+" if e["surprise_pct"] > 0 else ""
                lines.append(f"- {e['date']}: Est ${e['estimate']:.2f} → Act ${e['actual']:.2f} ({sign}{e['surprise_pct']:.1f}%)")

        # ── Agenda de eventos y hechos relevantes (lo que hace que Catalizadores
        # deje de girar solo alrededor del earnings) ──
        ev = eventos or {}
        agenda = ev.get("agenda") or []
        if agenda:
            lines.append("")
            lines.append("### AGENDA DE EVENTOS PRÓXIMOS (ordenada por cercanía):")
            for e in agenda[:12]:
                aprox = "  [~aprox: ventana estimada, NO confirmada]" if e.get("estimada") else ""
                desc = f" — {e.get('desc', '')}" if e.get("desc") else ""
                lines.append(
                    f"- {e.get('fecha')} (en {e.get('dias')} días) · "
                    f"[{e.get('tipo', '')}] **{e.get('titulo', '')}**{desc}{aprox}")

        hechos = ev.get("hechos_recientes") or []
        if hechos:
            lines.append("")
            lines.append("### HECHOS RELEVANTES RECIENTES (comunicados oficiales a la SEC):")
            for h in hechos[:8]:
                desc = f" — {h.get('desc', '')}" if h.get("desc") else ""
                lines.append(
                    f"- {h.get('fecha')} (hace {h.get('dias')} días) · "
                    f"**{h.get('titulo', '')}**{desc}")

        # ── Noticias (compartidas por sentimiento y catalizadores) ──
        if news:
            lines.append("")
            lines.append(f"## 3) SENTIMIENTO — Noticias Recientes ({len(news)} artículos, más reciente primero)")
            for item in news:
                freshness = item.get("freshness", "")
                age = item.get("age_hours", 0)
                age_label = f"{age:.0f}h" if age < 48 else f"{age/24:.0f}d"
                lines.append(f"- {freshness} [{age_label}] **{item.get('publisher', '')}**: {item.get('title', '')}")
        else:
            lines.append("")
            lines.append("## 3) SENTIMIENTO — Sin noticias recientes disponibles")

        lines += [
            "",
            "Analiza los TRES dominios (macro, sentimiento, catalizadores) para esta acción "
            "y retorna el JSON con las 3 secciones. Máximo 3 pros y 3 cons por sección.",
        ]

        return "\n".join(l for l in lines if l is not None)

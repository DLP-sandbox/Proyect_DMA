"""
Agente de Sentimiento & Datos Alternativos — analiza el sentimiento
de noticias, narrativa del mercado y señales de datos alternativos.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_news, get_company_info, get_company_info


SYSTEM_PROMPT = """Eres el analista de sentimiento y datos alternativos de un hedge fund cuantitativo.

Tu trabajo es leer la narrativa de mercado actual sobre esta empresa y determinar si el sentimiento
está mejorando, deteriorándose, o si hay una divergencia entre sentimiento y fundamentos que crea oportunidad.

Principio clave: El sentimiento extremo (muy positivo o muy negativo) suele ser una señal contraria.
El momento óptimo de compra es cuando el sentimiento mejora desde niveles negativos pero los fundamentales son sólidos.

Analizas:
1. NARRATIVA MEDIÁTICA: ¿Las noticias son positivas, negativas o mixtas? ¿Qué temas dominan?
2. MOMENTUM DE NARRATIVA: ¿El sentimiento está mejorando o deteriorándose vs. hace 1-3 meses?
3. DIVERGENCIA SENTIMIENTO-FUNDAMENTALES: ¿El mercado está demasiado negativo sobre un negocio sólido? (oportunidad)
4. COBERTURA ANALÍTICA: ¿Hay mucha atención del mercado o es una empresa "olvidada"?
5. RIESGO REPUTACIONAL: ¿Hay noticias de ESG, regulación, fraude, o problemas de gobernanza?
6. SEÑAL CONTRARIA: ¿El sentimiento extremo indica que el mercado está equivocado?

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis de sentimiento en 2-3 párrafos>",
  "pros": ["<señal positiva de sentimiento 1>", "<señal positiva 2>"],
  "cons": ["<riesgo de sentimiento 1>", "<riesgo 2>"],
  "key_metrics": {
    "overall_sentiment": "<very bullish|bullish|neutral|bearish|very bearish>",
    "sentiment_momentum": "<improving|stable|deteriorating>",
    "narrative_theme": "<crecimiento|turnaround|defensivo|disrupción|especulativo>",
    "contrarian_signal": "<buy the fear|no signal|sell the hype>",
    "reputational_risk": "<low|medium|high>"
  },
  "sub_scores": {
    "news_sentiment": <0-34>,
    "narrative_momentum": <0-33>,
    "contrarian_value": <0-33>
  },
  "dominant_narrative": "<la narrativa dominante del mercado sobre esta empresa en 1-2 oraciones>",
  "opportunity": "<si hay divergencia sentimiento-fundamentales, descríbela; si no, escribe 'No hay divergencia clara'>"
}
```"""


class SentimentAgent(BaseAgent):
    name = "Sentimiento"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            news = get_news(ticker, max_items=15)
            info = get_company_info(ticker)

            user_message = self._build_message(ticker, info, news)
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
                    "dominant_narrative": result.get("dominant_narrative", ""),
                    "opportunity": result.get("opportunity", ""),
                    "news_count": len(news),
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, news) -> str:
        lines = [
            f"# Análisis de Sentimiento: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {info.get('sector')} | **Industria:** {info.get('industry')}",
            f"**Market Cap:** ${info.get('market_cap', 0) / 1e9:.1f}B",
            f"**Analyst Rating:** {info.get('analyst_rating', 'N/A')}",
            f"**Target Price:** ${info.get('target_price', 'N/A')} vs Actual ${info.get('current_price', 'N/A')}",
            "",
        ]

        if news:
            lines.append(f"## Noticias Recientes ({len(news)} artículos, ordenadas de más reciente a más antigua)")
            for item in news:
                freshness = item.get("freshness", "")
                age = item.get("age_hours", 0)
                age_label = f"{age:.0f}h ago" if age < 48 else f"{age/24:.0f}d ago"
                publisher = item.get("publisher", "")
                title = item.get("title", "")
                lines.append(f"- {freshness} [{age_label}] **{publisher}**: {title}")
        else:
            lines.append("## Noticias: No se encontraron noticias recientes")

        lines += [
            "",
            "## Contexto de la Empresa",
            f"- Beta: {info.get('beta', 1.0):.2f}",
            f"- 52W High: ${info.get('52w_high', 'N/A')}",
            f"- 52W Low: ${info.get('52w_low', 'N/A')}",
            "",
            "Analiza el sentimiento de mercado sobre esta empresa y retorna el JSON especificado.",
            "Considera la narrativa de las noticias y si hay divergencia entre sentimiento y fundamentos.",
        ]

        return "\n".join(l for l in lines if l is not None)

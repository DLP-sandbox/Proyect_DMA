"""
Agente de Viabilidad Futura — analiza si el negocio tiene futuro real:
TAM/SAM, moat competitivo, riesgos de disrupción (AI, regulación, competidores)
y calidad del management. Usa noticias + descripción del negocio.
"""
import anthropic

from agents.base import BaseAgent, AgentReport
from data.market_data import get_company_info, get_news, get_financials, compute_quality_ratios


SYSTEM_PROMPT = """Eres el Director de Estrategia e Inversiones de un fondo de capital de largo plazo, con experiencia similar a la de los mejores inversores fundamentales de largo plazo (Charlie Munger, Terry Smith, Nick Sleep).

Tu trabajo es determinar si este negocio tiene un futuro brillante o si está en riesgo de obsolescencia, disrupción o deterioro.

Evalúas con perspectiva de 3-7 años:
1. MOAT / VENTAJA COMPETITIVA: ¿Tiene pricing power? ¿Network effects? ¿Switching costs? ¿Intangibles? ¿Escala?
2. TAM & PENETRACIÓN: ¿El mercado total es grande y creciente? ¿Cuánto ha penetrado ya?
3. DISRUPTION RISK: ¿Puede la AI, nueva tecnología o competidor emergente destruir el modelo de negocio en 5 años?
4. CALIDAD DEL MANAGEMENT: ¿El equipo directivo es capital allocator excelente? ¿Insider ownership alineado?
5. TAILWINDS SECTORIALES: ¿El viento sopla a favor o en contra del sector?
6. MODELO DE NEGOCIO: ¿Es escalable? ¿Recurring revenue? ¿Alta retención? ¿Negocio de buena calidad?
7. NARRATIVA DE MERCADO: ¿La narrativa del mercado está mejorando o deteriorándose?

Scoring guide (escala continua 0-100, granular, sin clustering en valores típicos):

- 88-97: COMPOUND MACHINE clarísimo — moat amplio + management excepcional + TAM enorme + disruption risk bajo + reinversión interna a alta TIR. Ejemplos: Microsoft, Visa/Mastercard, ASML, Constellation Software. El score exacto refleja qué tan únicas son las ventajas (Microsoft con IA hoy: 92-95; ASML monopolio EUV: 90-93).
- 78-87: Empresa excepcional con moat claro y management fuerte, pero con algún riesgo identificable (TAM saturándose, competencia emergente manejable).
- 66-77: Buen negocio con ventajas competitivas, runway de crecimiento decente. El score exacto refleja la fortaleza del moat y la dirección del momentum del negocio.
- 53-65: Empresa promedio del sector, sin edge estructural claro pero tampoco roto.
- 38-52: Mediocre o en transición incierta o con disruption risk medio.
- 25-37: Disrupción visible, moat erosionándose o management cuestionable.
- 0-24: Negocio en declive estructural o con alto riesgo de disrupción AI/tech.

REGLA ANTI-CLUSTERING: dos empresas distintas NUNCA deben tener el mismo score. No te ancles en 72, 75, 80. Da scores únicos que reflejen las particularidades cuantitativas (ej: 71, 74, 78, 83, no todos 75).

IMPORTANTE: Los COMPOUNDERS no necesitan catalizadores inmediatos. Su tesis es "comprar y mantener 5-10 años". No los castigues por timing técnico. Si el negocio reúne las características de compound machine (moat wide + management excellent + disruption risk low + reinversión interna), puntúalos 85+.

Retorna SIEMPRE este JSON:
```json
{
  "score": <0-100>,
  "conviction": "<HIGH|MEDIUM|LOW>",
  "analysis": "<análisis de viabilidad futura CONCISO: 1-2 párrafos, máximo 6 líneas en total. Directo al grano, sin relleno>",
  "pros": ["<ventaja futura 1>", "<ventaja futura 2>", "<ventaja futura 3>"],
  "cons": ["<riesgo futuro 1>", "<riesgo futuro 2>"],
  "key_metrics": {
    "moat_type": "<pricing power|network effects|switching costs|cost advantage|intangibles|none>",
    "moat_strength": "<wide|narrow|none>",
    "disruption_risk": "<low|medium|high|critical>",
    "tam_growth": "<expanding rapidly|expanding|stable|contracting>",
    "management_quality": "<excellent|good|average|poor>",
    "business_model": "<SaaS|marketplace|platform|traditional|commodity|other>"
  },
  "sub_scores": {
    "moat_quality": <0-25>,
    "growth_runway": <0-25>,
    "disruption_resilience": <0-25>,
    "management_capital_allocation": <0-25>
  },
  "future_thesis": "<en 2-3 oraciones, por qué este negocio vale más o menos en 5 años>",
  "key_risks": ["<riesgo crítico 1>", "<riesgo crítico 2>"]
}
```"""


class FutureViabilityAgent(BaseAgent):
    name = "Viabilidad Futura"

    def analyze(self, ticker: str, data: dict = None) -> AgentReport:
        try:
            info = get_company_info(ticker)
            news = get_news(ticker, max_items=10)
            financials = get_financials(ticker)
            ratios = compute_quality_ratios(info, financials)

            user_message = self._build_message(ticker, info, news, ratios)
            result = self._call_claude(SYSTEM_PROMPT, user_message)

            if "error" in result and "score" not in result:
                return self._safe_report(ticker, result.get("error", "Error"))

            sub_scores = result.get("sub_scores", {})
            future_snowflake = (
                sub_scores.get("moat_quality", 12) +
                sub_scores.get("growth_runway", 12)
            ) / 50 * 20

            return AgentReport(
                agent_name=self.name,
                score=float(result.get("score", 50)),
                analysis=result.get("analysis", ""),
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                key_metrics=result.get("key_metrics", {}),
                conviction=result.get("conviction", "MEDIUM"),
                sub_scores={**sub_scores, "future_snowflake": future_snowflake},
                raw_data={
                    "future_thesis": result.get("future_thesis", ""),
                    "key_risks": result.get("key_risks", []),
                    "moat_type": result.get("key_metrics", {}).get("moat_type", "unknown"),
                },
            )
        except Exception as e:
            return self._safe_report(ticker, str(e))

    def _build_message(self, ticker, info, news, ratios) -> str:
        lines = [
            f"# Análisis de Viabilidad Futura: {ticker} — {info.get('name', ticker)}",
            f"**Sector:** {info.get('sector')} | **Industria:** {info.get('industry')}",
            "",
            "## Descripción del Negocio",
            info.get("description", "No disponible")[:1500] if info.get("description") else "Descripción no disponible",
            "",
            "## Métricas Clave de Calidad",
            f"- Gross Margin: {ratios.get('gross_margin', 'N/A'):.1f}%" if ratios.get('gross_margin') else "- Gross Margin: N/A",
            f"- Operating Margin: {ratios.get('operating_margin', 'N/A'):.1f}%" if ratios.get('operating_margin') else "- Operating Margin: N/A",
            f"- Revenue CAGR 2Y: {ratios.get('revenue_cagr_2y', 'N/A'):.1f}%" if ratios.get('revenue_cagr_2y') else "- Revenue CAGR 2Y: N/A",
            f"- ROIC: {ratios.get('roic', 'N/A'):.1f}%" if ratios.get('roic') else "- ROIC: N/A",
            f"- FCF Yield: {ratios.get('fcf_yield', 'N/A'):.1f}%" if ratios.get('fcf_yield') else "- FCF Yield: N/A",
            "",
        ]

        if news:
            lines.append("## Noticias Recientes (últimas 10)")
            for item in news[:10]:
                lines.append(f"- [{item.get('date', '')[:10]}] **{item.get('publisher', '')}**: {item.get('title', '')}")

        lines += [
            "",
            "## Contexto Adicional",
            f"- Empleados: {info.get('employees', 'N/A'):,}" if info.get('employees') else "- Empleados: N/A",
            f"- Market Cap: ${info.get('market_cap', 0) / 1e9:.1f}B",
            f"- Beta: {info.get('beta', 1.0):.2f}",
            f"- Dividend Yield: {(info.get('dividend_yield', 0) or 0) * 100:.1f}%",
            "",
            "Analiza la viabilidad futura de este negocio con perspectiva de 3-7 años y retorna el JSON especificado.",
        ]

        return "\n".join(l for l in lines if l is not None)

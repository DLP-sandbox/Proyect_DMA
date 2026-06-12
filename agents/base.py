"""
Clase base para todos los sub-agentes. Define el contrato de análisis
y la interfaz con el Claude API usando prompt caching.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import anthropic

from config.settings import SUBAGENT_MODEL, MAX_TOKENS_AGENT


# ── Contexto temporal — inyectado en cada llamada a Claude ──────────────
SPANISH_DAYS = {
    "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles",
    "Thursday": "jueves", "Friday": "viernes", "Saturday": "sábado", "Sunday": "domingo",
}
SPANISH_MONTHS = {
    "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
    "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
    "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre",
}


def today_context() -> str:
    """
    Construye el header de contexto temporal que se inyecta a TODOS los agentes.
    Garantiza que cada análisis sepa exactamente la fecha y hora actual,
    para que priorice información reciente y evalúe correctamente eventos futuros.
    También adjunta la Guía de Redacción Club DLP (DLP_STYLE_GUIDE).
    """
    now = datetime.now()
    day_en = now.strftime("%A")
    month_en = now.strftime("%B")
    day_es = SPANISH_DAYS.get(day_en, day_en)
    month_es = SPANISH_MONTHS.get(month_en, month_en)

    date_str = f"{day_es}, {now.day} de {month_es} de {now.year}"
    iso_date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    in_2_days = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    in_1_week = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    in_2_weeks = (now + timedelta(days=14)).strftime("%Y-%m-%d")
    in_1_month = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    quarter = (now.month - 1) // 3 + 1

    # Próxima sesión hábil (saltando fines de semana)
    next_session = now + timedelta(days=1)
    while next_session.weekday() >= 5:
        next_session += timedelta(days=1)
    next_session_str = next_session.strftime("%Y-%m-%d (%A)")

    is_weekend = now.weekday() >= 5
    market_status = "🔴 MERCADO CERRADO (fin de semana)" if is_weekend else "🟢 MERCADO HÁBIL"

    return f"""## ⏱ CONTEXTO TEMPORAL — REFERENCIA OBLIGATORIA

**FECHA Y HORA ACTUAL DE LA CONSULTA:**
- Fecha: **{date_str}**
- ISO: **{iso_date}**
- Hora: {time_str}
- Trimestre fiscal: **Q{quarter} {now.year}**
- Estado del mercado US: {market_status}

**FECHAS FUTURAS DE REFERENCIA:**
- Próxima sesión hábil: {next_session_str}
- Mañana: {tomorrow}
- En 2 días: {in_2_days}
- En 1 semana: {in_1_week}
- En 2 semanas: {in_2_weeks}
- En 1 mes: {in_1_month}

⚠️ **INSTRUCCIONES TEMPORALES OBLIGATORIAS:**
1. Toda tu análisis debe entenderse como ACTUAL al {iso_date}.
2. PRIORIZA siempre la información más reciente sobre la histórica.
3. Para eventos futuros (earnings, catalizadores, lanzamientos), calcula días/semanas desde HOY ({iso_date}).
4. Si detectas datos antiguos o desactualizados, MENCIÓNALO explícitamente en tu análisis.
5. Tu conocimiento puede tener corte anterior — confía en los DATOS provistos como verdad actual.
6. Evalúa el horizonte temporal: ¿este evento es inminente (<7d), cercano (<30d) o lejano (>30d)?

---

{DLP_STYLE_GUIDE}
"""


# ── Guía de redacción Club DLP — inyectada a TODOS los agentes ──────────
# Esta guía define CÓMO se escribe el texto narrativo para la comunidad de
# inversores principiantes-intermedios del Club DLP. Se concatena dentro de
# today_context(), que ya se inyecta en los 9 agentes (8 sub + orquestador).
DLP_STYLE_GUIDE = """## ✍️ GUÍA DE REDACCIÓN — CLUB DLP (OBLIGATORIA, MÁXIMA PRIORIDAD)

Tus textos los leen inversores PRINCIPIANTES e INTERMEDIOS hispanohablantes, SIN
formación financiera, desde el celular. Tu trabajo NO es sonar como analista de
Wall Street. Tu trabajo es que CUALQUIER persona entienda, en español sencillo,
qué pasa con la empresa y por qué le importa a su dinero. Analizas con rigor de
experto, pero ESCRIBES como un amigo que sabe del tema y se lo explica claro y
fácil a otro amigo que recién empieza.

🔑 **REGLA DE ORO: no describas la métrica — explica QUÉ SIGNIFICA y POR QUÉ IMPORTA.**
  ❌ "El debt/equity es alto (2.5x)."
  ✅ "La empresa carga bastante deuda comparada con lo que realmente posee. Eso la
     hace más frágil: si el negocio se complica o suben las tasas de interés, esa
     deuda pesa mucho y puede meterla en problemas."
  ❌ "ROIC de 25%, muy por encima del sector."
  ✅ "Por cada dólar que la empresa invierte, genera muy buen retorno. Es señal de
     un negocio de calidad que usa bien su dinero."
  ❌ "RSI en 82, zona de sobrecompra."
  ✅ "La acción subió muy rápido en poco tiempo. Cuando eso pasa, suele venir una
     pausa o una bajada, así que conviene no entrar con prisa."

**REGLAS (aplican a TODOS los textos narrativos):**
1. TODO en español simple. NADA de términos en inglés en el texto. No escribas
   "moat", "earnings", "guidance", "debt to equity", "free cash flow", "ROIC",
   "P/E", etc. Descríbelo en español natural enfocándote en lo que significa:
   "su ventaja frente a la competencia", "los resultados del trimestre", "lo que
   la empresa proyecta ganar", "su nivel de deuda", "el dinero libre que le queda".
   NUNCA inventes traducciones raras (no escribas "foso" por moat) — describe el
   CONCEPTO en español claro.
2. Cada número va con su significado humano: ¿es bueno, malo, caro, barato,
   riesgoso, sólido? Ej: "Cotiza a 45 veces sus ganancias de un año — bastante
   caro; el mercado ya espera mucho crecimiento de ella."
3. Frases cortas. Ideas simples. Como hablándole a alguien que recién empieza a
   invertir. Nada de párrafos densos ni jerga.
4. Tono cercano, honesto y directo. Primera persona plural ("vemos", "creemos",
   "preferimos"). Nunca vendedor, académico ni alarmista. Sin euforia ni pánico,
   sin superlativos vacíos ("brutal", "histórico") salvo que un dato lo respalde.
5. Nunca digas "compra" o "vende" directo. Comparte la postura: "nos parece
   interesante", "preferimos esperar", "no lo vemos como oportunidad ahora".
6. Lenguaje de INVERSIÓN de largo plazo, NO de trading especulativo: escribe
   "nivel de protección" (no "stop loss"); "precio objetivo" (no "take profit");
   "tomar posición" o "invertir" (no "tradear" ni "operar").
7. NO menciones "la comunidad", "el Club DLP", "principiantes" ni "esta guía"
   dentro del texto. Solo aplica el estilo de forma natural.

⚠️ **REGLAS CRÍTICAS DE FORMATO (NO ROMPER — la app depende de esto):**
- Todo lo de arriba aplica SOLO a los textos narrativos (analysis, pros, cons,
  thesis, insights, strategy, verdict, macro_verdict, dominant_narrative,
  top_catalyst, future_thesis, key_insight, opportunity, etc.).
- NO traduzcas ni cambies los VALORES CORTOS de "key_metrics" (moat_strength,
  market_environment, sentiment_momentum, disruption_risk, stage, macd_signal,
  etc.). Esos van EXACTAMENTE en su forma corta en inglés ("wide", "low",
  "bullish", "risk-on", "improving", "neutral"). El dashboard los lee literalmente
  y los traduce solo para mostrarlos. Si los cambias, se ROMPE la app.
- NO cambies el formato JSON, los nombres de los campos, ni los valores de
  "score", "sub_scores", "recommendation" ni "conviction".

---

"""


# Refuerzo breve que se anexa al SYSTEM PROMPT de cada agente (el system pesa
# más en el tono que el mensaje de usuario). Determinista → cacheable.
DLP_STYLE_REMINDER = """

---
✍️ RECORDATORIO ESTILO CLUB DLP (MÁXIMA PRIORIDAD EN LA REDACCIÓN):

🚫 PALABRAS PROHIBIDAS en los textos narrativos — NO las escribas, usa el español:
  • "moat" → "su ventaja frente a la competencia"
  • "earnings" → "los resultados / las ganancias del trimestre"
  • "compounder" → "una empresa de calidad que crece de forma sostenida"
  • "pricing power" → "poder para subir precios sin perder clientes"
  • "ROIC" / "ROE" → "el retorno que saca del dinero que invierte"
  • "P/E" / "forward P/E" → "lo caro o barato que está según sus ganancias"
  • "FCF" / "free cash flow" → "el dinero libre que le queda"
  • "debt to equity" / "debt/equity" → "su nivel de deuda frente a lo que posee"
  • "EV/EBITDA" → "qué tan cara está según lo que genera operando"
  • "guidance" → "lo que la empresa proyecta ganar"
  • "RSI" → "qué tan rápido/acelerado viene subiendo"
  • "stop loss" → "nivel de protección"; "take profit" → "precio objetivo"
  • "YoY" → "frente al año pasado / anual"; "TTM" → "en los últimos 12 meses"
  • "beats" / "beat" → "superó lo esperado"; "best-in-class" → "de los mejores del sector"
  • "bargain" → "está barata / a buen precio"; "cheap/expensive" → "barata/cara"
  • "upside" → "potencial de subida"; "downside" → "riesgo de bajada"
  • "up/down" → "sube/baja"; "oversold" → "muy castigada"; "overbought" → "muy subida"
  • "rally" → "fuerte subida"; "sell-off" → "fuerte caída"; "growth" → "crecimiento"
  • "CPU/GPU" están bien (son productos), pero explica de qué tratan si hace falta.
  En general: si ves CUALQUIER palabra en inglés en tu texto, reemplázala por su
  equivalente en español. El texto final NO debe tener ni una sola palabra en inglés
  (excepto nombres propios de empresas/productos).

🔑 REGLA DE ORO (la más importante): NO nombres la métrica — di la CONCLUSIÓN en
lenguaje cotidiano. Traduce los números a una frase que cualquiera entienda:
  ❌ "Tiene ROE y ROIC altos."
  ✅ "Es una empresa altamente rentable: saca muy buen provecho del dinero que maneja."
  ❌ "Márgenes brutos de 77%."
  ✅ "De cada venta le queda muchísima ganancia — es un negocio muy eficiente."
  ❌ "Crece ingresos 24% anual con FCF sólido."
  ✅ "Crece rápido y genera bastante dinero libre cada año — un negocio sano y en expansión."
Habla como un amigo que sabe del tema y te lo explica fácil: frases cortas, español
simple y natural, primera persona ("vemos"). Nunca digas comprar/vender directo.

⚠️ EXCEPCIÓN: los VALORES CORTOS de key_metrics (moat_strength, market_environment,
sentiment_momentum, stage, etc.) SÍ van EXACTAMENTE en inglés ("wide", "bullish",
"risk-on", "improving") — el dashboard los necesita literales. No cambies el JSON,
los scores, recommendation ni conviction.

🎯 SCORING ANTI-CLUSTERING (REGLA CRÍTICA):
NO uses scores típicos de banda (72, 65, 80, 50). Da scores PRECISOS con granularidad
de 1-3 puntos basados en evidencia cuantitativa real. Cada análisis es único: dos empresas
nunca tienen exactamente el mismo perfil. Si dudas entre 70 y 75, usa 71, 73, 74 según
qué tan cerca esté la evidencia de uno u otro extremo. Evita repetir 72, 75, 80 entre
análisis distintos. Calibra a la baja: 60 no es "promedio", es "mediocre"; 75 no es
"bueno", es "muy bueno claramente por encima del sector"; 85 es excepcional. Usa toda
la escala 30-95 con precisión decimal-style (aunque enteros), no te encajones en bandas."""


@dataclass
class AgentReport:
    agent_name: str
    score: float                        # 0–100
    analysis: str                       # Análisis narrativo detallado
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    key_metrics: dict[str, Any] = field(default_factory=dict)
    conviction: str = "MEDIUM"          # HIGH / MEDIUM / LOW
    sub_scores: dict[str, float] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_name":  self.agent_name,
            "score":       self.score,
            "analysis":    self.analysis,
            "pros":        self.pros,
            "cons":        self.cons,
            "key_metrics": self.key_metrics,
            "conviction":  self.conviction,
            "sub_scores":  self.sub_scores,
            "raw_data":    self.raw_data,
            "error":       self.error,
        }


class BaseAgent:
    name: str = "BaseAgent"
    model: str = SUBAGENT_MODEL

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def analyze(self, ticker: str, data: dict) -> AgentReport:
        raise NotImplementedError

    def _call_claude(self, system_prompt: str, user_message: str, max_tokens: int = MAX_TOKENS_AGENT) -> dict:
        """Llama a Claude y parsea la respuesta JSON.
        Inyecta contexto temporal + guía de estilo DLP automáticamente:
        - today_context() (que incluye DLP_STYLE_GUIDE) al inicio del user message
        - DLP_STYLE_REMINDER al final del system prompt (refuerzo cacheable)."""
        try:
            full_user_message = today_context() + user_message
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt + DLP_STYLE_REMINDER,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": full_user_message}],
            )
            raw = response.content[0].text
            return self._parse_json(raw)
        except Exception as e:
            return {"error": str(e), "score": 50, "analysis": f"Error en análisis: {e}", "pros": [], "cons": []}

    def _parse_json(self, text: str) -> dict:
        """Extrae el primer bloque JSON de la respuesta."""
        # Intenta bloque ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Intenta JSON inline (primer { ... })
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"error": "No se pudo parsear JSON", "raw": text, "score": 50, "analysis": text, "pros": [], "cons": []}

    def _format_number(self, value, decimals: int = 2, suffix: str = "") -> str:
        if value is None:
            return "N/A"
        if abs(value) >= 1e9:
            return f"${value/1e9:.1f}B{suffix}"
        if abs(value) >= 1e6:
            return f"${value/1e6:.1f}M{suffix}"
        return f"{value:.{decimals}f}{suffix}"

    def _safe_report(self, ticker: str, error: str) -> AgentReport:
        return AgentReport(
            agent_name=self.name,
            score=50,
            analysis=("No pudimos completar esta parte del análisis porque faltaron "
                      "datos suficientes. Te recomendamos volver a intentarlo en un "
                      "momento; a veces la fuente de datos tarda en responder."),
            pros=[],
            cons=["Por ahora no tenemos datos suficientes para sacar conclusiones aquí"],
            conviction="LOW",
            error=error,
        )

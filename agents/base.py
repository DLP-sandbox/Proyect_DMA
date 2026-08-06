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
**REGLAS (aplican a TODOS los textos narrativos):**
1. TODO en español simple. NADA de términos en inglés en el texto — ni "momentum",
   ni "beats", ni "Stage", ni "timing", ni "priced in", ni "earnings", ni "rally".
   Describe el CONCEPTO en español natural por su significado ("impulso", "superó
   lo esperado", "etapa de subida", "ya descontado en el precio"). NUNCA inventes
   traducciones raras (no escribas "foso" por moat).
   Siglas de indicadores (RSI, MACD, SMA, ATR): primero la explicación en español
   y la sigla entre paréntesis UNA vez: "viene subiendo muy acelerada (RSI 82)".
2. Cada número va con su significado humano: ¿es bueno, malo, caro, barato,
   riesgoso, sólido? Y remata con lo que implica para el lector: ¿interesarse,
   esperar o tener cuidado? Ej: "Cotiza a 45 veces sus ganancias de un año —
   bastante caro; el mercado ya espera mucho de ella, mejor no entrar con prisa."
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
  • "momentum" → "impulso"; "timing" → "el momento de entrada"
  • "Stage 1/2/3/4" → "etapa 1 (base) / 2 (subida sostenida) / 3 (techo) / 4 (bajada)"
  • "beats"/"beat" → "superó lo esperado"; "priced in" → "ya descontado en el precio"
  • "squeeze" → "subida forzada por cierres de apuestas en contra"
  • "hedge fund" → "fondo de inversión especializado"; "short interest" → "apuestas a la baja"
  • "rally" → "subida fuerte"; "sell-off" → "caída fuerte"; "pullback" → "retroceso"
  • "breakout" → "ruptura al alza"; "setup" → "configuración"; "drawdown" → "caída desde máximos"
  • "crowded trade" → "apuesta demasiado concurrida"; "re-rating" → "revalorización"
  • "earnings" → "los resultados"; "guidance" → "lo que la empresa proyecta ganar"
  • "moat" → "su ventaja frente a la competencia"; "pricing power" → "poder de subir precios"
  • "upside" → "potencial de subida"; "downside" → "riesgo de bajada"
  • "oversold" → "muy castigada"; "overbought" → "muy subida"
  • "stop loss" → "nivel de protección"; "take profit" → "precio objetivo"
  • "FCF" → "el dinero libre que genera"; "YoY" → "frente al año pasado"
  En general: NI UNA palabra en inglés en el texto final (excepto nombres propios
  de empresas y productos).

📐 SIGLAS DE INDICADORES (RSI, MACD, SMA, ATR): primero la explicación en español;
la sigla, entre paréntesis UNA sola vez, con su valor:
  ✅ "viene subiendo muy acelerada (RSI 82) — suele venir una pausa"
  ✅ "cruzó al alza su indicador de impulso (MACD)"
  ❌ "RSI en 82, MACD alcista, sobre la SMA 50"

🔑 REGLA DE ORO (la más importante): NO nombres la métrica — di la CONCLUSIÓN en
lenguaje cotidiano y qué significa para el dinero del lector:
  ❌ "Tiene ROE y ROIC altos."
  ✅ "Es una empresa altamente rentable: saca muy buen provecho del dinero que maneja."
  ❌ "Márgenes brutos de 77%."
  ✅ "De cada venta le queda muchísima ganancia — es un negocio muy eficiente."
Cierra cada análisis respondiendo lo que el lector se pregunta de verdad: ¿esto es
momento de interesarse, de esperar o de tener cuidado? (sin decir comprar/vender
directo). Frases cortas, español natural, primera persona ("vemos").

⚠️ EXCEPCIÓN: los VALORES CORTOS de key_metrics (moat_strength, market_environment,
sentiment_momentum, stage, etc.) SÍ van EXACTAMENTE en inglés ("wide", "bullish",
"risk-on", "improving") — el dashboard los necesita literales. No cambies el JSON,
los scores, recommendation ni conviction.

🎯 SCORING ANTI-CLUSTERING (REGLA CRÍTICA):
Nada de scores de banda (72, 65, 80, 50): cifras PRECISAS, granularidad de 1-3 puntos,
basadas en evidencia cuantitativa. Si dudas entre 70 y 75, usa 71, 73 o 74 según dónde
caiga la evidencia. Calibra a la baja: 60 no es "promedio", es "mediocre"; 75 es "muy
bueno, claramente por encima del sector"; 85 es excepcional. Usa toda la escala 30-95.

📊 DATOS AUSENTES ("N/A") — PROHIBIDO PUNTUARLOS Y PROHIBIDO MENCIONARLOS:
1) Puntúa SOLO con los datos que SÍ tienes, repartiendo el peso entre ellos. Un dato en
   N/A —o que no aplica al sector, como el margen bruto o el EBITDA en un banco— JAMÁS
   baja el score. "No disponible" NO es "malo": es simplemente un dato que no existe.
2) NUNCA escribas un "con", un "pro", un riesgo ni una frase del análisis que hable de
   lo que falta. Están PROHIBIDAS las frases tipo "no hay datos de X", "falta
   visibilidad sobre Y", "ausencia de información/data sobre Z", "análisis incompleto",
   "sin claridad sobre W", "no se puede evaluar V". Si un dato no está, NO lo nombres:
   escribe solo sobre lo que SÍ sabes.
3) Si un pilar entero se queda sin datos, dale la mitad de la escala (neutro) y punto."""


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


# ── Parseo robusto de JSON de las respuestas de Claude ──────────────────
# Los modelos (sobre todo Haiku) suelen escribir los campos narrativos con
# SALTOS DE LÍNEA LITERALES dentro del string (ej: "analysis" en 1-2 párrafos).
# json.loads en modo estricto rechaza esos caracteres de control ("Invalid
# control character"), lo que hacía fallar el parseo y volcar el JSON crudo en
# pantalla. Estas utilidades toleran esos casos y reparan JSON truncado, sin
# cambiar el comportamiento para respuestas ya válidas. (Portadas de la versión
# L-DLP-Analysis, donde ya están probadas en producción.)

def _close_truncated_json(s: str) -> str:
    """Cierra strings/objetos/arrays que quedaron abiertos por truncado."""
    in_str = False
    esc = False
    stack = []
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    out = s
    if in_str:
        out += '"'
    out = re.sub(r",\s*$", "", out.rstrip())
    for ch in reversed(stack):
        out += "}" if ch == "{" else "]"
    return out


def _lenient_json_loads(s: str):
    """json.loads tolerante: permite saltos de línea literales (strict=False),
    quita comas colgantes y repara truncados. Devuelve dict o None."""
    s = s.strip()
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", s)
    for cand in (s, no_trailing, _close_truncated_json(s), _close_truncated_json(no_trailing)):
        try:
            obj = json.loads(cand, strict=False)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _first_balanced_object(text: str):
    """Devuelve el primer objeto JSON balanceado (respeta strings: una llave
    dentro de la prosa no desincroniza el conteo). Si quedó truncado, devuelve
    desde la primera '{' hasta el final para repararlo luego."""
    start = text.find("{")
    if start == -1:
        return None
    in_str = False
    esc = False
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def extract_json_dict(text: str):
    """Extrae de forma robusta el primer objeto JSON de `text`. dict o None."""
    candidates = []
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if m:
        candidates.append(m.group(1))
    balanced = _first_balanced_object(text)
    if balanced:
        candidates.append(balanced)
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        candidates.append(m.group(0))
    for cand in candidates:
        obj = _lenient_json_loads(cand)
        if obj is not None:
            return obj
    return None


def salvage_analysis_text(text: str) -> str:
    """Rescata SÓLO el texto del campo 'analysis' de un JSON irrecuperable.
    Nunca devuelve el JSON crudo: si no hay nada rescatable, un mensaje limpio."""
    m = re.search(r'"analysis"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if m:
        try:
            val = json.loads('"' + m.group(1) + '"', strict=False).strip()
            if len(val) >= 20:
                return val
        except Exception:
            pass
    # Truncado: desde "analysis": " hasta el próximo campo o el final del texto
    m = re.search(r'"analysis"\s*:\s*"(.+?)(?="\s*,\s*"\w+"\s*:|"\s*\}|$)', text, re.DOTALL)
    if m:
        val = re.sub(r"\\[nrt]", " ", m.group(1))
        val = val.replace('\\"', '"').replace("\\", "").strip().strip('"').strip()
        if len(val) >= 20:
            return val
    return ("No pudimos generar la conclusión de este análisis en este intento. "
            "Vuelve a ejecutarlo en un momento; a veces la fuente de datos o el "
            "modelo tardan en responder.")


def _looks_like_leaked_json(text: str) -> bool:
    """True SÓLO si el texto es claramente un volcado de JSON crudo (no prosa).

    Conservador a propósito: una conclusión normal en español nunca empieza con
    '{' o '```', ni contiene claves JSON literales como `"analysis":`. Así es
    imposible tocar por error un análisis bien formado. Incluye las claves del
    ORQUESTADOR (`investment_thesis`/`composite_score`): su volcado no contiene
    `"analysis"` y se escapaba del guard original."""
    if not text:
        return False
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("```"):
        return True
    # Claves JSON literales de un reporte serializado (los keys van en inglés;
    # la prosa en español usaría «análisis» con tilde, nunca `"analysis":`).
    return re.search(
        r'"(analysis|score|conviction|investment_thesis|composite_score)"\s*:',
        text) is not None


def sanitize_leaked_json_text(text: str) -> str:
    """Si `text` es un JSON crudo filtrado (bug de análisis viejos guardados),
    devuelve SÓLO la conclusión limpia. Si es prosa normal, lo deja intacto.

    No muta datos: se aplica al cargar/mostrar, extrayendo el texto real sobre
    la marcha. Para texto ya limpio es un no-op."""
    if not isinstance(text, str) or not _looks_like_leaked_json(text):
        return text
    obj = extract_json_dict(text)
    if obj is not None:
        # Volcado de agente → campo "analysis"; volcado del orquestador → la
        # tesis vive en "investment_thesis". Se rescata la que exista.
        for k in ("analysis", "investment_thesis"):
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return salvage_analysis_text(text)


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
        """Extrae y parsea el JSON de la respuesta del modelo, de forma robusta.

        `extract_json_dict` tolera saltos de línea literales dentro de los
        strings, comas colgantes, prosa después del bloque y JSON TRUNCADO por
        max_tokens (los cuatro modos de fallo vistos en producción). Si aun así
        no se puede parsear, se recuperan score/convicción por regex y el texto
        con `salvage_analysis_text` — NUNCA se vuelca el JSON crudo en pantalla
        ni se deja el análisis en blanco."""
        obj = extract_json_dict(text)
        if obj is not None:
            return obj

        # ── Último recurso: recuperar los campos sueltos. Nunca el texto crudo.
        def _field(name: str) -> str:
            mm = re.search(r'"' + name + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if not mm:
                return ""
            try:
                return json.loads('"' + mm.group(1) + '"', strict=False)
            except Exception:
                return mm.group(1)

        def _score() -> float:
            mm = re.search(r'"score"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
            try:
                return float(mm.group(1)) if mm else 50
            except Exception:
                return 50

        return {
            "error":      "JSON malformado (recuperado por campos)",
            "score":      _score(),
            "conviction": _field("conviction") or "MEDIUM",
            "analysis":   salvage_analysis_text(text),
            "pros":       [],
            "cons":       [],
        }

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

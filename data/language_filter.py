"""
Filtro determinista de jerga inglesa residual (COSTO $0 — sin IA, sin red).

POR QUÉ EXISTE
--------------
Los prompts de sistema de los agentes están escritos con vocabulario financiero
en inglés (moat, ROIC, upside, earnings…). Eso "primea" a Haiku para que filtre
esos términos en el texto narrativo en español ~30% de las veces. En vez de
reescribir 5 prompts (riesgo de romper el scoring/JSON), aplicamos un reemplazo
determinista SOLO sobre el texto narrativo, justo antes de mostrarlo/guardarlo.

GARANTÍAS DE SEGURIDAD (prioridad máxima — no romper nada)
----------------------------------------------------------
1. SOLO toca campos NARRATIVOS (tesis, pros, cons, estrategias). NUNCA toca
   `key_metrics`, `raw_data`, `sub_scores`, los enums (`quality_verdict`,
   `asymmetry_direction`, `recommendation`, `conviction_level`…) ni los números.
   → El dashboard sigue recibiendo sus valores literales en inglés intactos.
2. Es determinista y reversible: borrar la llamada = volver al comportamiento de
   hoy. No añade dependencias (solo `re` de la stdlib).
3. Idempotente: correrlo 2 veces da el mismo resultado (las traducciones no
   contienen términos en inglés, así que no se re-traducen en cascada).
4. FALLBACK TOTAL: cualquier error se traga → se devuelve el texto original sin
   tocar. Nunca crashea ni bloquea el render.
"""
import re

# ── Acrónimos: case-SENSITIVE (solo mayúsculas) para no chocar con palabras
# españolas (p. ej. "roe" del verbo roer). El modelo siempre los escribe en
# mayúsculas, así que no perdemos cobertura. Las traducciones NO llevan artículo
# inicial para encajar en la gramática existente ("su ROE alto" → "su retorno
# sobre el patrimonio alto").
_ACRONYM_RULES = [
    (r"\bP/E ratio\b",  "relación precio-ganancia"),
    (r"\bPE ratio\b",   "relación precio-ganancia"),
    (r"\bforward P/E\b","relación precio-ganancia estimada"),
    (r"\btrailing P/E\b","relación precio-ganancia actual"),
    (r"\bP/E\b",        "relación precio-ganancia"),
    (r"\bROIC\b",       "retorno sobre el capital"),
    (r"\bROCE\b",       "retorno sobre el capital empleado"),
    (r"\bROE\b",        "retorno sobre el patrimonio"),
    (r"\bROA\b",        "retorno sobre los activos"),
    (r"\bFCF\b",        "flujo de caja libre"),
    (r"\bEPS\b",        "ganancia por acción"),
    (r"\bCAGR\b",       "crecimiento anual compuesto"),
    (r"\bYoY\b",        "interanual"),
    (r"\bYOY\b",        "interanual"),
    (r"\bQoQ\b",        "de un trimestre a otro"),
    (r"\bTTM\b",        "de los últimos 12 meses"),
]

# ── Siglas de indicadores técnicos: la decisión pactada es "explicación primero,
# sigla entre paréntesis UNA vez": «viene subiendo muy acelerada (RSI 68)».
# El lookbehind (?<!\() evita re-tocar una sigla que YA está entre paréntesis —
# eso hace las reglas idempotentes y respeta los textos que el modelo ya escribe
# bien. Los reemplazos empiezan por sustantivo con género estable ("indicador",
# "media") para que la concordancia del artículo previo funcione o no haga falta.
_INDICATOR_RULES = [
    # Si el modelo YA escribió "indicador/índice RSI", no duplicar "indicador"
    (r"(?<!\()\b[Ii]ndicador\s+RSI\b",  "indicador de aceleración (RSI)"),
    (r"(?<!\()\b[Ii]ndicador\s+MACD\b", "indicador de impulso (MACD)"),
    (r"(?<!\()\b[Íí]ndice\s+RSI\b",     "indicador de aceleración (RSI)"),
    # Específicos primero (más contexto → mejor español)
    (r"(?<!\()\bSMA\s*20\b",  "media móvil de 20 días (SMA 20)"),
    (r"(?<!\()\bSMA\s*50\b",  "media móvil de 50 días (SMA 50)"),
    (r"(?<!\()\bSMA\s*150\b", "media móvil de 150 días (SMA 150)"),
    (r"(?<!\()\bSMA\s*200\b", "media móvil de 200 días (SMA 200)"),
    (r"(?<!\()\bRSI\b",       "indicador de aceleración (RSI)"),
    (r"(?<!\()\bMACD\b",      "indicador de impulso (MACD)"),
    (r"(?<!\()\bSMA\b",       "media móvil (SMA)"),
    (r"(?<!\()\bEMA\b",       "media móvil exponencial (EMA)"),
    (r"(?<!\()\bATR\b",       "medida de volatilidad (ATR)"),
    (r"(?<!\()\bOBV\b",       "indicador de volumen acumulado (OBV)"),
]

# ── Etapas del ciclo (Stan Weinstein). El modelo escribe "Stage 2" a secas; el
# lector principiante no sabe qué es. Cada etapa lleva su significado UNA vez.
_STAGE_RULES = [
    (r"(?<!\()\bStage\s*1\b", "etapa 1 (formación de base)"),
    (r"(?<!\()\bStage\s*2\b", "etapa 2 (subida sostenida)"),
    (r"(?<!\()\bStage\s*3\b", "etapa 3 (techo)"),
    (r"(?<!\()\bStage\s*4\b", "etapa 4 (bajada)"),
    (r"\bStage\b",            "etapa"),
]

# ── Palabras: case-INSENSITIVE. ORDEN IMPORTA (más específico primero) para que
# "earnings call" se traduzca antes que "earnings" suelto.
_WORD_RULES = [
    # ── Auto-reparación: textos ya guardados que una versión anterior del
    # filtro dejó con duplicaciones. Idempotentes y sin falsos positivos.
    (r"\bindicador\s+indicador\b",                 "indicador"),
    (r"\bmomento\s+de\s+entrada\s+para\s+entrar\b", "momento para entrar"),
    # ── Bloque original ──
    (r"earnings\s+call",  "presentación de resultados"),
    (r"earnings\s+report","informe de resultados"),
    (r"\bearnings\b",     "resultados"),
    (r"\bguidance\b",     "previsiones"),
    (r"\bmoats\b",        "ventajas competitivas"),
    (r"\bmoat\b",         "ventaja competitiva"),
    (r"\bcompounders\b",  "empresas que componen su valor"),
    (r"\bcompounder\b",   "empresa que compone su valor"),
    (r"\bupside\b",       "potencial de subida"),
    (r"\bdownside\b",     "riesgo de caída"),
    (r"\bbullish\b",      "alcista"),
    (r"\bbearish\b",      "bajista"),
    (r"\bbargain\b",      "precio de ganga"),
    (r"\bovervalued\b",   "sobrevalorada"),
    (r"\bundervalued\b",  "infravalorada"),
    (r"best[- ]in[- ]class", "el mejor de su categoría"),

    # ── Ampliación guiada por la auditoría real (26-44 fugas/análisis) ──
    # ORDEN: lo compuesto va antes que la palabra suelta. Los reemplazos evitan
    # empezar por artículo (el original suele traerlo: "el momentum" → "el
    # impulso") y, cuando el sustantivo es femenino, su cabeza está registrada
    # en _FEM_HEAD para que la concordancia del artículo se corrija sola.
    (r"\bmomentum\b",         "impulso"),
    (r"\bbeats?\s+consecutivos\b", "trimestres consecutivos superando lo esperado"),
    (r"\bbeat\s+rate\b",      "tasa de aciertos"),
    (r"\bbeats\b",            "resultados por encima de lo esperado"),
    (r"\bbeat\b",             "superó lo esperado"),
    # "ya priced in" → sin duplicar el "ya"; "priced in en el precio" → sin
    # duplicar el complemento (el modelo a veces ya lo escribe redundante)
    (r"\bya\s+priced[- ]in\b(\s+en\s+el\s+precio\b)?", "ya descontado en el precio"),
    (r"\bpriced[- ]in\b(\s+en\s+el\s+precio\b)?",       "descontado en el precio"),
    (r"\bre[- ]rating\b",     "revalorización del múltiplo"),
    (r"\bshort\s+squeeze\b",  "subida forzada por cierres de apuestas en contra"),
    (r"\bsqueeze\b",          "subida forzada por cierres de apuestas en contra"),
    (r"\bhedge\s+funds\b",    "fondos de inversión especializados"),
    (r"\bhedge\s+fund\b",     "fondo de inversión especializado"),
    (r"\brally\b",            "subida fuerte"),
    (r"\bsell[- ]?offs?\b",   "caída fuerte del mercado"),
    (r"\bpullbacks?\b",       "retroceso"),
    (r"\bbreakouts?\b",       "ruptura al alza"),
    (r"\boversold\b",         "sobrevendida"),
    (r"\boverbought\b",       "sobrecomprada"),
    # "timing de entrada" / "timing para entrar" → sin duplicar el complemento
    (r"\btiming\s+de\s+entrada\b",  "momento de entrada"),
    (r"\btiming\s+para\s+entrar\b", "momento para entrar"),
    (r"\btiming\b",           "momento de entrada"),
    (r"\bsetups?\b",          "configuración técnica"),
    (r"\btriggers?\b",        "detonante"),
    (r"\bdrawdowns?\b",       "caída desde máximos"),
    (r"\bcrowded\s+trade\b",  "apuesta demasiado concurrida"),
    (r"\bshort\s+interest\b", "nivel de apuestas a la baja"),
    (r"\bswing\s+low\b",      "mínimo reciente"),
    (r"\bswing\s+high\b",     "máximo reciente"),
    (r"\bfree\s+cash\s+flow\b", "flujo de caja libre"),
    (r"\bcash\s+flow\b",      "flujo de caja"),
    (r"\brevenue\s+growth\b", "crecimiento de ingresos"),
    (r"\brevenue\b",          "ingresos"),
    (r"\bentorno\s+risk[- ]on\b",  "entorno de apetito por el riesgo"),
    (r"\bentorno\s+risk[- ]off\b", "entorno de aversión al riesgo"),
    (r"\brisk[- ]on\b",       "apetito por el riesgo"),
    (r"\brisk[- ]off\b",      "aversión al riesgo"),
    (r"\bcatalysts\b",        "catalizadores"),
    (r"\bcatalyst\b",         "catalizador"),
]

# Compilamos una sola vez al importar (rendimiento). Cada entrada es
# (patrón_compilado, reemplazo). Los indicadores van case-SENSITIVE (el modelo
# los escribe siempre en mayúsculas y así no chocamos con palabras españolas);
# las etapas y palabras, case-insensitive.
_COMPILED = (
    [(re.compile(p), r) for p, r in _ACRONYM_RULES]
    + [(re.compile(p), r) for p, r in _INDICATOR_RULES]
    + [(re.compile(p, re.IGNORECASE), r) for p, r in _STAGE_RULES]
    + [(re.compile(p, re.IGNORECASE), r) for p, r in _WORD_RULES]
)

# Caracteres "neutros" que pueden preceder a un término sin que deje de ser
# inicio de oración (comillas, paréntesis, viñetas, signos de apertura).
_LEADING_NEUTRAL = " \t\"'“”‘’(¡¿*-—•·>"


def _make_replacer(replacement: str):
    """Devuelve una función de reemplazo que capitaliza la traducción SOLO si el
    término traducido cae al inicio de una oración (para no romper la mayúscula
    inicial). En medio de la frase va en minúscula."""
    def _repl(m: "re.Match") -> str:
        s = m.string
        i = m.start()
        j = i - 1
        while j >= 0 and s[j] in _LEADING_NEUTRAL:
            j -= 1
        at_sentence_start = (j < 0) or (s[j] in ".!?\n:")
        if at_sentence_start:
            return replacement[:1].upper() + replacement[1:]
        return replacement
    return _repl


# ── Pase de concordancia: como las traducciones introducen sustantivos con un
# género fijo (conocido de antemano), corregimos el artículo que las precede
# para no dejar errores como "un relación" → "una relación". Solo tocamos los
# artículos directamente delante de un sustantivo FEMENINO conocido. La
# concordancia del adjetivo que va después (p. ej. "bajo"→"baja") depende del
# contexto y se deja como está (sigue siendo español entendible).
# OJO con el orden dentro de la alternación: la forma larga antes que su prefijo
# (ventajas|ventaja, apuestas|apuesta) para que el plural no se corte a mitad.
_FEM_HEAD = (r"(relación|ventajas|ventaja|ganancias|ganancia|presentación|"
             r"empresas|empresa|subida|caídas|caída|ruptura|configuración|"
             r"revalorización|apuestas|apuesta|tasa|medias|media|medida|etapa)")


def _art_replacer(target: str):
    """Reemplaza el artículo por su forma femenina, preservando la mayúscula
    inicial del original ('Un'→'Una', 'el'→'la')."""
    def _r(m: "re.Match") -> str:
        original_article = m.group(0)[: m.group(0).lower().find(m.group(1).lower())].strip()
        head = m.group(1)
        new_art = target
        if original_article[:1].isupper():
            new_art = new_art[:1].upper() + new_art[1:]
        return f"{new_art} {head}"
    return _r


_AGREEMENT_RULES = [
    (re.compile(r"\b[Uu]n\s+" + _FEM_HEAD + r"\b", re.IGNORECASE), _art_replacer("una")),
    (re.compile(r"\b[Ee]l\s+" + _FEM_HEAD + r"\b", re.IGNORECASE), _art_replacer("la")),
    (re.compile(r"\b[Dd]el\s+" + _FEM_HEAD + r"\b", re.IGNORECASE), _art_replacer("de la")),
    (re.compile(r"\b[Aa]l\s+" + _FEM_HEAD + r"\b", re.IGNORECASE), _art_replacer("a la")),
]


_EUPHONY = re.compile(r"\by\s+(?=[iI]ndicador)")


def _fix_agreement(text: str) -> str:
    for pattern, repl in _AGREEMENT_RULES:
        text = pattern.sub(repl, text)
    # Eufonía del español: "y" → "e" delante de palabra que empieza por i-
    # (solo la aplicamos a los sustantivos que nosotros mismos introducimos).
    text = _EUPHONY.sub("e ", text)
    return text


def _strip_raw_json(text):
    """Rescata el texto limpio de un análisis que quedó CACHEADO como JSON crudo.

    Delegado en `sanitize_leaked_json_text` (agents.base), que cubre más casos
    que la versión anterior de esta función: volcados con prosa por delante,
    JSON truncado, saltos de línea literales dentro de los strings y volcados
    del ORQUESTADOR (claves investment_thesis/composite_score, sin "analysis").
    El contrato se mantiene: prosa normal = no-op; ante cualquier error, el
    texto original intacto."""
    if not text or not isinstance(text, str):
        return text
    try:
        from agents.base import sanitize_leaked_json_text
        return sanitize_leaked_json_text(text)
    except Exception:
        return text


def _clean_text(text):
    """Aplica todas las reglas a un string. Devuelve el texto tal cual si no es
    string o si está vacío. Primero rescata el análisis de un posible JSON crudo
    cacheado (así ningún análisis viejo muestra el volcado con símbolos)."""
    if not text or not isinstance(text, str):
        return text
    text = _strip_raw_json(text)
    for pattern, replacement in _COMPILED:
        text = pattern.sub(_make_replacer(replacement), text)
    text = _fix_agreement(text)
    return text


# ── Ítems que se QUITAN: quejas sobre datos que faltan ────────────────────
# POR QUÉ. Cuando una acción no publica una métrica —o esa métrica no aplica a
# su sector, como el margen bruto o el EBITDA en un banco— el modelo tendía a
# convertir el hueco en un argumento en contra: «Falta transparencia en
# métricas clave: no hay datos de ROIC, EBITDA ni liquidez». Eso es castigar a
# la empresa por un vacío de información, no por su negocio. El recordatorio de
# estilo ya lo prohíbe, pero una instrucción a un modelo NUNCA es garantía:
# medido en un A/B real, la prohibición bajó los casos de 2 a 1, no a 0.
# Esta capa determinista ($0, sin IA) es la garantía de verdad.
#
# DOBLE SEÑAL para no llevarse por delante hechos legítimos del negocio: hace
# falta un marcador de AUSENCIA **y** que lo ausente sea un DATO o una MÉTRICA.
# Así «ausencia de dividendo» o «ausencia de nuevos fondos entrando» —que son
# hechos reales y deben quedarse— nunca se tocan, y en cambio «ausencia de
# datos sobre ROIC» o «ROIC desconocido» sí se van.
# El marcador de ausencia tiene que ir PEGADO a la palabra de dato (hasta dos
# palabras de relleno en medio), no solo aparecer en la misma frase. Con la
# versión laxa se colaban «sin depender de deuda», «sin compras compensatorias»
# y «sin deuda neta: el balance está limpio», que son hechos del negocio.
_MARCADOR = (r"(?:sin|falta de|faltan|falta|ausencia de|carece de|carecen de|"
             r"no hay|no existe[n]?|no se public[ao]|no report[ao]|no tenemos|"
             r"no conocemos|no sabemos)")
_DATO_PAL = (r"(?:datos?|data|informaci[oó]n|m[eé]tricas?|visibilidad|"
             r"transparencia|cifras?|detalle[s]?|desglose)")

_QUEJA_DATOS = re.compile(
    r"(" + _MARCADOR + r"\s+(?:\w+\s+){0,2}" + _DATO_PAL + r"|"
    r"\bN/A\b|no disponible[s]?|no est[aá]n? disponible[s]?|"
    r"(?:datos?|informaci[oó]n|an[aá]lisis)\s+incomplet[oa]s?|"
    r"incompletos?\s+(?:datos|por falta)|"
    r"no se puede[n]?\s+(?:evaluar|medir|calcular|verificar|confirmar|estimar)|"
    r"no podemos\s+(?:evaluar|medir|calcular|verificar|confirmar|estimar)|"
    r"(?:ROIC|ROE|ROA|EBITDA|FCF|EV/EBITDA|P/E|current ratio|quick ratio|"
    r"m[aá]rgen(?:es)?|liquidez)\s+(?:real\s+)?desconocid[oa]s?"
    r")", re.I)


def _es_queja_de_datos(texto):
    """True si el ítem es una queja sobre datos que faltan (y por tanto hay que
    quitarlo). Exige las DOS señales en la misma frase. NUNCA lanza."""
    try:
        if not isinstance(texto, str) or not texto.strip():
            return False
        return bool(_QUEJA_DATOS.search(texto))
    except Exception:
        return False


def _drop_quejas_de_datos(items):
    """Quita de una lista de pros/cons/riesgos los ítems que solo se quejan de
    datos ausentes. Si TODOS lo fueran, devuelve la lista original: preferimos
    un argumento imperfecto a una sección vacía. NUNCA lanza."""
    try:
        if not isinstance(items, list) or not items:
            return items
        quedan = [x for x in items if not _es_queja_de_datos(x)]
        return quedan if quedan else items
    except Exception:
        return items


def _clean_list(items):
    """Limpia cada string de una lista (deja intactos los no-string)."""
    if not isinstance(items, list):
        return items
    return [_clean_text(x) if isinstance(x, str) else x for x in items]


# Campos narrativos de StockAnalysis que SÍ se limpian.
_ANALYSIS_TEXT_FIELDS = (
    "investment_thesis", "entry_strategy", "exit_strategy",
    "time_horizon", "alpha_opportunity",
)
_ANALYSIS_LIST_FIELDS = ("key_strengths", "key_risks")

# ── LISTA BLANCA de campos narrativos dentro de raw_data ──────────────────
# La UI muestra estos textos en las tarjetas de insight de cada sección
# (dcf_thesis, macro_verdict, dominant_narrative…) y hasta ahora NO pasaban por
# el filtro — era una de las tres fugas de jerga detectadas en la auditoría.
# Es lista BLANCA a propósito: cualquier clave de raw_data que no esté aquí
# (números, dicts, enums como asymmetry_direction, datos de holders…) queda
# intacta, que es la garantía de siempre — el dashboard lee esos valores
# literalmente y traducirlos lo rompería.
_RAW_DATA_NARRATIVE_KEYS = (
    "key_insight", "top_catalyst", "macro_verdict", "dominant_narrative",
    "opportunity", "risk_verdict", "stop_rationale", "dcf_thesis",
    "earnings_quality", "future_thesis", "key_risks",
)


def clean_analysis_language(analysis):
    """Limpia la jerga inglesa residual de un StockAnalysis, SOLO en sus campos
    narrativos y en los .analysis/.pros/.cons de cada sub-reporte.

    NUNCA toca: key_metrics, raw_data, sub_scores, conviction, enums
    (quality_verdict, asymmetry_*, recommendation), snowflake, score_breakdown,
    vetos_applied ni ningún número → el dashboard sigue intacto.

    Muta el objeto in-place y lo devuelve. Ante CUALQUIER error, devuelve el
    objeto sin cambios (fallback total — nunca rompe el render)."""
    try:
        for attr in _ANALYSIS_TEXT_FIELDS:
            if hasattr(analysis, attr):
                setattr(analysis, attr, _clean_text(getattr(analysis, attr)))
        for attr in _ANALYSIS_LIST_FIELDS:
            if hasattr(analysis, attr):
                setattr(analysis, attr,
                        _drop_quejas_de_datos(_clean_list(getattr(analysis, attr))))

        reports = getattr(analysis, "reports", None)
        if isinstance(reports, dict):
            for rep in reports.values():
                if hasattr(rep, "analysis"):
                    rep.analysis = _clean_text(rep.analysis)
                # Los pros/cons pasan además por el filtro que QUITA las
                # quejas sobre datos ausentes (ver _drop_quejas_de_datos).
                if hasattr(rep, "pros"):
                    rep.pros = _drop_quejas_de_datos(_clean_list(rep.pros))
                if hasattr(rep, "cons"):
                    rep.cons = _drop_quejas_de_datos(_clean_list(rep.cons))
                # Campos narrativos de raw_data (LISTA BLANCA — ver arriba).
                # Solo strings o listas de strings; cualquier otro tipo se salta.
                rd = getattr(rep, "raw_data", None)
                if isinstance(rd, dict):
                    for k in _RAW_DATA_NARRATIVE_KEYS:
                        v = rd.get(k)
                        if isinstance(v, str):
                            rd[k] = _clean_text(v)
                        elif isinstance(v, list):
                            rd[k] = _clean_list(v)
    except Exception:
        pass
    return analysis

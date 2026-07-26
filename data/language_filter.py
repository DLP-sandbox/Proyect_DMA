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

# ── Palabras: case-INSENSITIVE. ORDEN IMPORTA (más específico primero) para que
# "earnings call" se traduzca antes que "earnings" suelto.
_WORD_RULES = [
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
]

# Compilamos una sola vez al importar (rendimiento). Cada entrada es
# (patrón_compilado, reemplazo).
_COMPILED = (
    [(re.compile(p), r) for p, r in _ACRONYM_RULES]
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
_FEM_HEAD = r"(relación|ventajas|ventaja|ganancia|presentación|empresas|empresa)"


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


def _fix_agreement(text: str) -> str:
    for pattern, repl in _AGREEMENT_RULES:
        text = pattern.sub(repl, text)
    return text


def _strip_raw_json(text):
    """Rescata el texto limpio de un análisis que quedó CACHEADO como JSON crudo.

    Algunos análisis viejos (generados antes del arreglo del parser) guardaron en
    `.analysis` el volcado completo del JSON del modelo — con llaves, `"score"`,
    prosa extra, etc. Aquí, SOLO si el texto claramente es ese volcado, extraemos
    el valor del campo `"analysis"`. Si no parece JSON, se devuelve intacto.
    Fallback total: ante cualquier error, el texto original."""
    if not text or not isinstance(text, str):
        return text
    t = text.strip()
    looks_json = (t.startswith("```") or t.startswith("{")) and '"analysis"' in t and '"score"' in t
    if not looks_json:
        return text
    try:
        import json as _json
        # 1) objeto balanceado desde el primer '{'
        start = t.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(t)):
                if t[i] == "{":
                    depth += 1
                elif t[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = _json.loads(t[start:i + 1])
                            if isinstance(obj, dict) and isinstance(obj.get("analysis"), str) and obj["analysis"].strip():
                                return obj["analysis"]
                        except Exception:
                            pass
                        break
        # 2) regex directo al campo "analysis"
        m = re.search(r'"analysis"\s*:\s*"((?:[^"\\]|\\.)*)"', t)
        if m:
            try:
                return _json.loads('"' + m.group(1) + '"')
            except Exception:
                return m.group(1)
    except Exception:
        pass
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
                setattr(analysis, attr, _clean_list(getattr(analysis, attr)))

        reports = getattr(analysis, "reports", None)
        if isinstance(reports, dict):
            for rep in reports.values():
                if hasattr(rep, "analysis"):
                    rep.analysis = _clean_text(rep.analysis)
                if hasattr(rep, "pros"):
                    rep.pros = _clean_list(rep.pros)
                if hasattr(rep, "cons"):
                    rep.cons = _clean_list(rep.cons)
    except Exception:
        pass
    return analysis

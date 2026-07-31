"""
Caché compartido de análisis vía Upstash Redis (REST API).

DISEÑO DE SEGURIDAD (prioridad máxima — no romper nada):
- Usa SOLO `requests` (ya instalado). NO requiere el paquete `redis` ni `supabase`
  → imposible que cause ImportError (el bug que rompió Supabase la vez pasada).
- Es un caché PURO y aislado: guarda/lee análisis por ticker con TTL de 30 días.
- TOTALMENTE OPCIONAL: si NO hay credenciales de Upstash en el entorno, TODAS las
  funciones son no-op. La app funciona EXACTAMENTE igual que sin caché. Esto lo
  hace 100% reversible: quitar las env vars = volver al comportamiento actual.
- FALLBACK TOTAL: cualquier error (red, timeout, parsing) se traga silenciosamente
  → get devuelve None (se genera análisis fresco) y save no hace nada. Nunca
  bloquea ni crashea la app.

Variables de entorno requeridas para activarlo:
  UPSTASH_REDIS_REST_URL   (ej: https://xxxx.upstash.io)
  UPSTASH_REDIS_REST_TOKEN (el token REST)
"""
import os
import json

import requests

# ── Dos ventanas distintas, y es a propósito ──────────────────────────────
# CACHE_TTL_SECONDS (30 días) = cuánto SOBREVIVE la fila en Redis.
# ANALYSIS_FRESH_HOURS (24 h)  = cuánto se REUTILIZA el análisis.
#
# ¿Por qué no son lo mismo? Porque la fila cumple DOS funciones:
#   1. Reutilizar el análisis para no gastar créditos → solo si tiene <24 h.
#   2. Repoblar el historial de la barra lateral cuando Render reinicia el
#      contenedor y se lleva el disco por delante (ver la hidratación en
#      dashboard/app.py). Para esto hace falta que la fila siga ahí.
# Si la fila expirara a las 24 h, el historial se perdería cada día. Así que se
# conserva 30 días y el filtro de edad se aplica al LEER (get_cached_analysis).
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 2,592,000 segundos = 30 días


def _config():
    """Devuelve (url, token) si ambas env vars están; si no, None (→ caché off)."""
    url = (os.getenv("UPSTASH_REDIS_REST_URL", "") or "").strip().rstrip("/")
    token = (os.getenv("UPSTASH_REDIS_REST_TOKEN", "") or "").strip()
    if url and token:
        return url, token
    return None


def is_enabled() -> bool:
    """True si el caché está configurado (hay credenciales)."""
    return _config() is not None


def _command(cmd: list, timeout: float = 4.0):
    """Ejecuta un comando Redis vía la REST API de Upstash (POST con el comando
    como array JSON en el body — maneja valores grandes sin problema).
    Devuelve el campo 'result', o None ante cualquier problema."""
    cfg = _config()
    if not cfg:
        return None
    url, token = cfg
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=cmd,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("result")
    except Exception:
        return None


def get_cached_analysis(ticker: str, solo_fresco: bool = True):
    """StockAnalysis del caché compartido, o None.

    `solo_fresco=True` (lo normal) devuelve None si el análisis tiene más de
    ANALYSIS_FRESH_HOURS: así el caller lo rehace desde cero. Este es el punto
    ÚNICO donde se filtra la edad para todos los que reutilizan un análisis.

    `solo_fresco=False` lo devuelve sin mirar la edad — lo usa la hidratación del
    historial de la barra lateral, que necesita los análisis viejos para poder
    LISTARLOS (al hacer clic en uno se rehará, pero primero tiene que aparecer).
    """
    if not _config():
        return None
    raw = _command(["GET", f"analysis:{ticker.upper()}"])
    if not raw:
        return None
    try:
        data = json.loads(raw)
        from data.persistence import stock_analysis_from_dict
        obj = stock_analysis_from_dict(data)
        # Solo válido si la tesis es real (no un fallback genérico)
        if not obj or len(getattr(obj, "investment_thesis", "") or "") <= 200:
            return None
        if solo_fresco and not analisis_fresco(obj):
            return None
        return obj
    except Exception:
        pass
    return None


def analisis_fresco(analysis) -> bool:
    """True si el análisis tiene menos de ANALYSIS_FRESH_HOURS.

    Ante una fecha ilegible o ausente devuelve False, que es el lado seguro:
    "no me consta que sea fresco" → se rehace. Nunca lanza.

    DESFASE HORARIO — por qué se toleran fechas "del futuro":
    los timestamps se guardan con `datetime.now()` SIN zona horaria, y el caché
    de Upstash lo comparten máquinas en husos distintos: Render corre en UTC y
    una revisión en local puede ir varias horas por detrás. Un análisis hecho en
    Render se leía aquí como si fuera del futuro (visto de verdad: +4 h) y se
    daba por caducado → se re-analizaba SIEMPRE, quemando créditos sin motivo.
    Y un análisis del futuro no puede estar viejo: si la fecha va por delante,
    lo único que pasa es que los relojes no coinciden. Así que se acepta un
    desfase de hasta ANALYSIS_FRESH_HOURS por delante (cubre los husos reales,
    máximo ±14 h) y más allá se considera fecha corrupta → se rehace.
    """
    try:
        from datetime import datetime
        from config.settings import ANALYSIS_FRESH_HOURS
        crudo = getattr(analysis, "timestamp", None)
        if not crudo:
            return False
        creado = datetime.fromisoformat(str(crudo)[:26])
        margen = float(ANALYSIS_FRESH_HOURS)
        horas = (datetime.now() - creado).total_seconds() / 3600.0
        return -margen < horas < margen
    except Exception:
        return False


def save_cached_analysis(ticker: str, analysis) -> None:
    """Guarda un análisis en el caché compartido con TTL de 30 días.
    No-op si no hay credenciales o si algo falla (fallback total)."""
    if not _config():
        return
    try:
        from data.persistence import _make_json_safe
        data = _make_json_safe(analysis.to_dict())
        value = json.dumps(data, ensure_ascii=False)
        _command(["SET", f"analysis:{ticker.upper()}", value,
                  "EX", str(CACHE_TTL_SECONDS)])
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# SNAPSHOT MACRO — el último registro bueno de índices y rotación sectorial
# ─────────────────────────────────────────────────────────────────────────
# `get_macro_data()` tarda ~4,4 s en frío y alimenta DOS bloques del inicio
# (Live Market Pulse + Rotación Sectorial), así que la página se quedaba
# esperando con una cinta de carga. Aquí se guarda el último registro para
# poder pintar el bloque AL INSTANTE y refrescar por detrás.
#
# Además da resistencia: get_macro_data usa yfinance SIN cadena de respaldo
# (la única función de datos que no la tiene), así que en Render —donde Yahoo
# bloquea las IPs de datacenter— `sector_performance` puede llegar vacío y la
# sección no se dibuja. Con el snapshot se sigue viendo el último dato bueno.
#
# NO lleva filtro de edad a propósito: su valor es justamente ser "lo último
# que se supo", por viejo que sea. Es compartido: el primer miembro que abre
# la app lo deja listo para todos los demás.

MACRO_SNAPSHOT_KEY = "macro:snapshot"
MACRO_SNAPSHOT_TTL = 7 * 24 * 60 * 60      # 7 días


def save_macro_snapshot(macro) -> None:
    """Guarda el último registro macro. Nunca lanza.

    Solo guarda si trae rotación sectorial real: así un fallo de red (que
    devuelve el dict a medias o vacío) JAMÁS pisa el último dato bueno."""
    try:
        if not isinstance(macro, dict) or not macro.get("sector_performance"):
            return
        from data.persistence import _make_json_safe
        datos = _make_json_safe(macro)
        try:
            _command(["SET", MACRO_SNAPSHOT_KEY,
                      json.dumps(datos, ensure_ascii=False),
                      "EX", str(MACRO_SNAPSHOT_TTL)])
        except Exception:
            pass
        try:
            from data.market_data import _save_cache
            _save_cache("macro_snapshot", datos)
        except Exception:
            pass
    except Exception:
        pass


def get_macro_snapshot():
    """Último registro macro conocido, o None. Nunca lanza.

    Mira primero Upstash (compartido) y luego el disco (para que en local, sin
    credenciales, funcione igual)."""
    try:
        crudo = _command(["GET", MACRO_SNAPSHOT_KEY])
        if crudo:
            datos = json.loads(crudo)
            if isinstance(datos, dict) and datos.get("sector_performance"):
                return datos
    except Exception:
        pass
    try:
        from data.market_data import _load_cache
        # TTL enorme: el snapshot no caduca, solo se sustituye por uno mejor.
        datos = _load_cache("macro_snapshot", ttl_hours=24 * 365)
        if isinstance(datos, dict) and datos.get("sector_performance"):
            return datos
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────
# HISTORIAL PERSISTENTE PARA LA BARRA LATERAL (Upstash — opcional, aislado)
# ─────────────────────────────────────────────────────────────────────────
# El disco de Streamlit Cloud es EFÍMERO: se borra al reiniciar el contenedor.
# Para que la barra lateral conserve "los últimos 10 análisis y 3 escaneos"
# entre reinicios, mantenemos un índice ligero en Redis:
#   · dlp:recent_analyses  → lista de tickers (más reciente al frente, cap 10).
#     El JSON de cada análisis ya vive en `analysis:{TICKER}` (arriba).
#   · dlp:recent_scans     → lista de scan_id (cap 3); cada scan completo en
#     `dlp:scan:{scan_id}` con TTL de 30 días.
# TODO aquí es no-op sin credenciales y traga cualquier error → jamás rompe
# ni bloquea la app. Borrar estas funciones = volver al comportamiento de hoy.

RECENT_ANALYSES_KEY = "dlp:recent_analyses"
RECENT_SCANS_KEY = "dlp:recent_scans"
MAX_RECENT_ANALYSES = 10
MAX_RECENT_SCANS = 3


def record_recent_analysis(ticker: str) -> None:
    """Empuja el ticker al frente del índice de análisis recientes (sin
    duplicados, cap 10). El JSON ya lo guarda save_cached_analysis()."""
    if not _config():
        return
    try:
        t = (ticker or "").upper().strip()
        if not t:
            return
        _command(["LREM", RECENT_ANALYSES_KEY, "0", t])
        _command(["LPUSH", RECENT_ANALYSES_KEY, t])
        _command(["LTRIM", RECENT_ANALYSES_KEY, "0", str(MAX_RECENT_ANALYSES - 1)])
    except Exception:
        pass


def get_recent_analysis_tickers() -> list:
    """Lista de tickers recientes (más reciente primero). [] sin creds/error."""
    if not _config():
        return []
    try:
        res = _command(["LRANGE", RECENT_ANALYSES_KEY, "0", str(MAX_RECENT_ANALYSES - 1)])
        return [str(x) for x in (res or [])]
    except Exception:
        return []


def save_cloud_scan(scan_id: str, data: dict) -> None:
    """Guarda un scan COMPLETO en Redis (TTL 30 días) e indexa su id (cap 3).
    `data` es el mismo dict que se guarda a disco (scan_id/timestamp/label/
    count/results). No-op sin creds; traga errores."""
    if not _config() or not scan_id:
        return
    try:
        from data.persistence import _make_json_safe
        value = json.dumps(_make_json_safe(data), ensure_ascii=False)
        # Guardias de tamaño: Upstash acepta valores grandes, pero evitamos
        # subir scans gigantescos (max_results altísimo) — con 400 candidatos
        # sobra para la vista de resultados.
        _command(["SET", f"dlp:scan:{scan_id}", value, "EX", str(CACHE_TTL_SECONDS)])
        _command(["LREM", RECENT_SCANS_KEY, "0", scan_id])
        _command(["LPUSH", RECENT_SCANS_KEY, scan_id])
        _command(["LTRIM", RECENT_SCANS_KEY, "0", str(MAX_RECENT_SCANS - 1)])
    except Exception:
        pass


def get_recent_cloud_scans() -> list:
    """Devuelve [(scan_id, label, count)] de los scans en la nube, más reciente
    primero. [] sin creds/error."""
    if not _config():
        return []
    out = []
    try:
        ids = _command(["LRANGE", RECENT_SCANS_KEY, "0", str(MAX_RECENT_SCANS - 1)]) or []
        for sid in ids:
            raw = _command(["GET", f"dlp:scan:{sid}"])
            if not raw:
                continue
            try:
                d = json.loads(raw)
                out.append((str(sid), d.get("label", str(sid)), int(d.get("count", 0) or 0)))
            except Exception:
                continue
    except Exception:
        return out
    return out


def get_cloud_scan_results(scan_id: str) -> list:
    """Devuelve la lista de dicts de ScreenerResult de un scan en la nube, o []."""
    if not _config() or not scan_id:
        return []
    try:
        raw = _command(["GET", f"dlp:scan:{scan_id}"])
        if not raw:
            return []
        return list(json.loads(raw).get("results", []) or [])
    except Exception:
        return []

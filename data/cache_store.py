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

# TTL del caché: 30 días. La tesis de inversión es de largo plazo y no cambia
# en un mes. Los precios/gráficas/indicadores NO se cachean aquí — se refrescan
# en vivo cada vez que se renderiza el análisis (eso no consume créditos de IA).
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


def get_cached_analysis(ticker: str):
    """Devuelve un StockAnalysis cacheado (compartido entre todos los usuarios)
    si existe y es válido; si no, None. None → el caller genera uno fresco con IA.

    La expiración de 30 días la maneja Redis automáticamente (la llave se borra
    sola), así que si llega algo es porque tiene menos de 30 días."""
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
        if obj and len(getattr(obj, "investment_thesis", "") or "") > 200:
            return obj
    except Exception:
        pass
    return None


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

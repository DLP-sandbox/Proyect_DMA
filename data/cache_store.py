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

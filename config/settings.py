import os
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (no depender del CWD)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# ── Anthropic ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Models: orchestrator usa Sonnet (mayor razonamiento), sub-agentes Haiku (velocidad)
ORCHESTRATOR_MODEL = "claude-sonnet-4-6"
SUBAGENT_MODEL = "claude-haiku-4-5-20251001"

# ── APIs opcionales ────────────────────────────────────────────────────────
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
FMP_API_KEY = os.getenv("FMP_API_KEY", "")

# ── Parámetros del sistema ─────────────────────────────────────────────────
CACHE_TTL_HOURS = 4          # Horas antes de refrescar datos cacheados
MAX_TOKENS_AGENT = 3000      # Max tokens por sub-agente (subido: explicar términos inline alarga el texto)
MAX_TOKENS_ORCHESTRATOR = 4500  # subido para evitar truncado del JSON con el estilo DLP

# Ponderaciones del Composite Score
# REBALANCEADO 2026: más peso a Fundamentales + Future (calidad LP)
# Menos peso a factores de corto plazo (institucional, catalizadores, sentimiento)
WEIGHTS = {
    "fundamentals":   0.22,   # ↑ +2 (calidad estructural)
    "future":         0.22,   # ↑ +7 (largo plazo es CLAVE)
    "technical":      0.14,   # ↓ -1 (timing)
    "institutional":  0.12,   # ↓ -3
    "catalysts":      0.12,   # ↓ -3
    "macro":          0.10,   # =
    "sentiment":      0.08,   # ↓ -2
}

# Umbrales de recomendación (renombrados a español)
THRESHOLDS = {
    "MUY ATRACTIVO":   85,
    "ATRACTIVO":       70,
    "EN OBSERVACIÓN":  50,
    "EVITAR":           0,
}

# Screener — filtros básicos de universo (legacy fallback cuando no se pasan filtros custom)
SCREENER_FILTERS = {
    "min_price":       10.0,
    "min_avg_volume":  500_000,
    "min_market_cap":  1_000_000_000,   # 1B USD
    "min_rs_percentile": 60,            # Relative Strength mínimo vs S&P500
}

# Máximo de candidatos que pasan al análisis profundo
MAX_DEEP_ANALYSIS = 20


# ── Scanner personalizable — Defaults UI ──────────────────────────────────
# Estos defaults aproximan el comportamiento histórico del screener.
# El UI lee/escribe estos valores en st.session_state.scanner_filters.
SCANNER_DEFAULTS = {
    # Tamaño de la empresa — lista de buckets activos (multi-select)
    "size_buckets": ["mega", "grande", "mediana", "pequena", "micro"],
    # Tendencia técnica — lista de stages activos (multi-select)
    "stages": [1, 2],
    # Fortaleza relativa vs S&P 500 — single
    "rs_strength": "fuerte",          # muy_fuerte | fuerte | promedio | debil | cualquiera
    # Momentum últimos 6 meses — single
    "momentum_6m": "cualquiera",      # aceleracion | positivo | negativo | cualquiera
    # Cercanía al máximo anual — single
    "proximity_high": "cualquiera",   # cerca | media | lejos | cualquiera
    # Sectores de interés — lista (multi-select). [] = todos
    "sectors": [],
    # Liquidez mínima — single
    "liquidity": "media",             # alta | media | baja
    # Cantidad de resultados — single
    "max_results": 20,                # 20 | 50 | 100 | 9999 (todos)
}

# Catálogo de sectores soportados (deben matchear los strings que devuelve yfinance)
SECTOR_OPTIONS = [
    "Technology",
    "Healthcare",
    "Financial Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Communication Services",
    "Industrials",
    "Energy",
    "Real Estate",
    "Utilities",
    "Basic Materials",
]

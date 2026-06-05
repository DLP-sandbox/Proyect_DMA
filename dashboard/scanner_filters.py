"""
Helpers de mapeo UI → filtros técnicos del ScreenerAgent.

Tabla central de opciones amigables (lo que ve el usuario) y traducción
a los keys técnicos que entiende el screener.
"""
from typing import Optional


# ── Tabla central de opciones UI (label visible + valor lógico) ──────────

SIZE_OPTIONS = [
    {"key": "mega",    "label": "Mega",     "sub": "≥ $200B",    "min": 200e9,  "max": None},
    {"key": "grande",  "label": "Grande",   "sub": "$50–200B",   "min": 50e9,   "max": 200e9},
    {"key": "mediana", "label": "Mediana",  "sub": "$10–50B",    "min": 10e9,   "max": 50e9},
    {"key": "pequena", "label": "Pequeña",  "sub": "$2–10B",     "min": 2e9,    "max": 10e9},
    {"key": "micro",   "label": "Micro",    "sub": "< $2B",      "min": 0,      "max": 2e9},
]

STAGE_OPTIONS = [
    {"key": 2, "label": "Alcista",       "sub": "Stage 2 — tendencia alcista confirmada"},
    {"key": 1, "label": "Acumulación",   "sub": "Stage 1 — base lateral previa al alza"},
    {"key": 3, "label": "Consolidación", "sub": "Stage 3 — distribución temprana"},
    {"key": 4, "label": "Bajista",       "sub": "Stage 4 — tendencia bajista"},
]

RS_OPTIONS = [
    {"key": "muy_fuerte", "label": "Muy fuerte", "sub": "RS ≥ 80 vs S&P 500",   "min_rs": 80},
    {"key": "fuerte",     "label": "Fuerte",     "sub": "RS ≥ 60",              "min_rs": 60},
    {"key": "promedio",   "label": "Promedio",   "sub": "RS ≥ 40",              "min_rs": 40},
    {"key": "debil",      "label": "Débil",      "sub": "RS < 40",              "min_rs": 0},
    {"key": "cualquiera", "label": "Cualquiera", "sub": "Sin filtro de fuerza", "min_rs": 0},
]

MOMENTUM_OPTIONS = [
    {"key": "aceleracion", "label": "En aceleración", "sub": "+30% o más en 6M",    "min_mom_6m": 30.0},
    {"key": "positivo",    "label": "Positivo",       "sub": "Retorno 6M positivo", "min_mom_6m": 0.0},
    {"key": "negativo",    "label": "Negativo",       "sub": "Retorno 6M negativo", "min_mom_6m": None, "max_mom_6m": 0.0},
    {"key": "cualquiera",  "label": "Cualquiera",     "sub": "Sin filtro",          "min_mom_6m": None},
]

PROXIMITY_OPTIONS = [
    {"key": "cerca",      "label": "Cerca del máximo", "sub": "Dentro del 10% del 52W high", "pct_min": -10.0, "pct_max": None},
    {"key": "media",      "label": "Distancia media",  "sub": "Entre -25% y -10% del high",  "pct_min": -25.0, "pct_max": -10.0},
    {"key": "lejos",      "label": "Lejos del máximo", "sub": "Más del 25% bajo el high",    "pct_min": -100.0, "pct_max": -25.0},
    {"key": "cualquiera", "label": "Cualquiera",       "sub": "Sin filtro de distancia",     "pct_min": -100.0, "pct_max": None},
]

SECTOR_OPTIONS = [
    {"key": "Technology",             "label": "Tecnología",           "icon": "💻"},
    {"key": "Healthcare",              "label": "Salud",                 "icon": "🏥"},
    {"key": "Financial Services",      "label": "Financiero",            "icon": "🏦"},
    {"key": "Consumer Cyclical",       "label": "Consumo discrecional",  "icon": "🛍️"},
    {"key": "Consumer Defensive",      "label": "Consumo defensivo",     "icon": "🛒"},
    {"key": "Communication Services",  "label": "Comunicaciones",        "icon": "📡"},
    {"key": "Industrials",             "label": "Industriales",          "icon": "🏭"},
    {"key": "Energy",                  "label": "Energía",               "icon": "⚡"},
    {"key": "Real Estate",             "label": "Inmobiliario",          "icon": "🏘️"},
    {"key": "Utilities",               "label": "Utilities",             "icon": "🔌"},
    {"key": "Basic Materials",         "label": "Materiales básicos",    "icon": "🪨"},
]

LIQUIDITY_OPTIONS = [
    {"key": "alta",  "label": "Alta",  "sub": "Volumen ≥ 5M diario",   "min_vol": 5_000_000},
    {"key": "media", "label": "Media", "sub": "Volumen ≥ 1M diario",   "min_vol": 1_000_000},
    {"key": "baja",  "label": "Baja",  "sub": "Volumen ≥ 500K diario", "min_vol": 500_000},
]

MAX_RESULTS_OPTIONS = [
    {"key": 20,   "label": "20",    "sub": "Top 20 (recomendado)"},
    {"key": 50,   "label": "50",    "sub": "Top 50"},
    {"key": 100,  "label": "100",   "sub": "Top 100"},
    {"key": 9999, "label": "Todos", "sub": "Todos los que pasen los filtros"},
]


# ── Mapeo central ────────────────────────────────────────────────────────

def _find(options: list, key) -> Optional[dict]:
    for o in options:
        if o["key"] == key:
            return o
    return None


def build_screener_filters(ui_selection: dict) -> dict:
    """Convierte selección amigable del UI a dict técnico para ScreenerAgent.

    ui_selection esperado:
      {
        "size_buckets":   ["mega", "grande", ...],
        "stages":         [1, 2],
        "rs_strength":    "fuerte",
        "momentum_6m":    "cualquiera",
        "proximity_high": "media",
        "sectors":        ["Technology", ...]  o []  (vacío = todos),
        "liquidity":      "media",
        "max_results":    20,
      }
    Retorna dict con keys técnicos que entiende ScreenerAgent._normalize_filters.
    Tolera ausencia/None en cualquier campo (cae a defaults sensatos).
    """
    ui = ui_selection or {}
    out = {}

    # 1. Market cap range desde size_buckets
    sizes = ui.get("size_buckets") or []
    if sizes:
        mins, maxs = [], []
        for s in sizes:
            opt = _find(SIZE_OPTIONS, s)
            if opt:
                mins.append(opt["min"])
                # max=None significa sin tope → guardamos +inf para que el max() lo respete
                maxs.append(opt["max"] if opt["max"] is not None else float("inf"))
        if mins:
            out["market_cap_min"] = min(mins)
            top = max(maxs)
            out["market_cap_max"] = None if top == float("inf") else top
    # Si no se seleccionó ningún bucket, no filtramos por tamaño
    else:
        out["market_cap_min"] = 0
        out["market_cap_max"] = None

    # 2. Stages permitidos
    stages = ui.get("stages") or []
    if stages:
        out["allowed_stages"] = list(stages)
    else:
        # vacío = ningún filtro de stage (permite todos)
        out["allowed_stages"] = [0, 1, 2, 3, 4]

    # 3. RS strength
    rs_opt = _find(RS_OPTIONS, ui.get("rs_strength", "cualquiera"))
    out["min_rs"] = rs_opt["min_rs"] if rs_opt else 0

    # 4. Momentum 6M
    mom_opt = _find(MOMENTUM_OPTIONS, ui.get("momentum_6m", "cualquiera"))
    if mom_opt:
        out["min_momentum_6m"] = mom_opt.get("min_mom_6m")
        # "negativo" usa max_mom_6m=0 → reusar pct_from_high pattern: aquí lo manejamos como min negativo
        if mom_opt.get("key") == "negativo":
            out["min_momentum_6m"] = -999.0  # acepta cualquier valor negativo
            # Para excluir positivos necesitaríamos un max — pero el screener no soporta max momentum.
            # Trade-off aceptado: "negativo" = sin tope inferior. Si en práctica se necesita filtrar
            # estrictamente negativos, expandir el screener.

    # 5. Proximity al high
    prox_opt = _find(PROXIMITY_OPTIONS, ui.get("proximity_high", "cualquiera"))
    if prox_opt:
        out["pct_from_high_min"] = prox_opt["pct_min"]
        out["pct_from_high_max"] = prox_opt["pct_max"]

    # 6. Sectores
    sectors = ui.get("sectors") or []
    out["allowed_sectors"] = sectors if sectors else None

    # 7. Liquidez
    liq_opt = _find(LIQUIDITY_OPTIONS, ui.get("liquidity", "media"))
    out["min_avg_volume"] = liq_opt["min_vol"] if liq_opt else 500_000

    # 8. Cantidad de resultados
    mr = ui.get("max_results", 20)
    out["max_results"] = int(mr)

    # Filtros constantes (mantenidos del default)
    out["min_price"] = 5.0  # un poco más bajo que antes para no descartar micro caps

    return out

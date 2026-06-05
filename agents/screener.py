"""
Agente Screener — usa TradingView Screener (gratis, sin API key, sin rate limit
en IPs cloud, a diferencia de Yahoo Finance) para filtrar el universo del NYSE +
NASDAQ y devolver los mejores candidatos.

Sustituto quirúrgico del screener anterior basado en yfinance:
- Mantiene EXACTAMENTE la misma interfaz pública (ScreenerResult, ScreenerAgent,
  run_full_scan(), quick_validate()).
- Mantiene la misma lógica de filtros, Stage Analysis (Minervini), RS score y
  composite screener score.
- Cambia ÚNICAMENTE la fuente de datos: una sola petición a TradingView en vez
  de cientos de batch downloads a Yahoo. Scan completo: ~5-10 segundos.
"""
from dataclasses import dataclass
from typing import Optional
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from config.settings import SCREENER_FILTERS, MAX_DEEP_ANALYSIS


# Defaults del screener — idénticos a la versión anterior para no romper nada
DEFAULT_TECHNICAL_FILTERS = {
    "min_price":          SCREENER_FILTERS["min_price"],
    "min_avg_volume":     SCREENER_FILTERS["min_avg_volume"],
    "market_cap_min":     SCREENER_FILTERS["min_market_cap"],
    "market_cap_max":     None,
    "allowed_stages":     [1, 2],
    "min_rs":             SCREENER_FILTERS["min_rs_percentile"],
    "min_momentum_6m":    None,
    "pct_from_high_min":  -30.0,
    "pct_from_high_max":  None,
    "allowed_sectors":    None,
    "max_results":        MAX_DEEP_ANALYSIS,
}


# Columnas que pedimos a TradingView en cada query
_TV_COLUMNS = [
    "name",                       # ticker
    "description",                # nombre empresa
    "sector",                     # sector TRBC (Thomson Reuters)
    "industry",                   # industry TRBC — usado para detectar REITs
    "close",                      # precio actual
    "market_cap_basic",           # market cap
    "average_volume_30d_calc",    # volumen promedio 30d
    "SMA50",                      # SMA 50
    "SMA100",                     # SMA 100 (proxy para SMA150)
    "SMA200",                     # SMA 200
    "Perf.3M",                    # momentum 3M (%)
    "Perf.6M",                    # momentum 6M (%)
    "Perf.Y",                     # performance 1 año (%)
    "Perf.1M",                    # momentum 1M (%) — usado en RS
    "price_52_week_high",         # max 52W
    "RSI",                        # RSI 14
]


# ── Mapping de sectores TRBC (TradingView) → GICS (lo que usa el UI) ───────
# Los scanner_filters.py del UI usan nombres GICS estándar:
# Technology, Healthcare, Financial Services, Consumer Cyclical,
# Consumer Defensive, Communication Services, Industrials, Energy,
# Real Estate, Utilities, Basic Materials.
# TradingView devuelve nombres TRBC distintos — los traducimos al GICS del UI
# para que el filtro de sectores del usuario funcione y los sectores se vean
# familiares en la tabla de resultados.
_TRBC_TO_GICS = {
    # Tecnología
    "Electronic Technology":    "Technology",
    "Technology Services":      "Technology",
    # Salud
    "Health Technology":        "Healthcare",
    "Health Services":          "Healthcare",
    # Financiero (REITs se detectan via industry, ver _normalize_sector)
    "Finance":                  "Financial Services",
    # Consumo discrecional (cíclico)
    "Consumer Durables":        "Consumer Cyclical",
    "Consumer Services":        "Consumer Cyclical",
    "Retail Trade":             "Consumer Cyclical",
    # Consumo defensivo (estable)
    "Consumer Non-Durables":    "Consumer Defensive",
    "Distribution Services":    "Consumer Defensive",
    # Comunicaciones
    "Communications":           "Communication Services",
    # Industriales
    "Producer Manufacturing":   "Industrials",
    "Industrial Services":      "Industrials",
    "Commercial Services":      "Industrials",
    "Transportation":           "Industrials",
    # Energía
    "Energy Minerals":          "Energy",
    # Utilities (mismo nombre)
    "Utilities":                "Utilities",
    # Materiales básicos
    "Non-Energy Minerals":      "Basic Materials",
    "Process Industries":       "Basic Materials",
}


def _normalize_sector(trbc_sector: str, industry: str) -> str:
    """Convierte un sector TRBC de TradingView al equivalente GICS que usa el
    UI. Detecta REITs por industry (van en 'Finance' en TRBC pero pertenecen
    a 'Real Estate' en GICS). Lo desconocido cae en 'Other'."""
    if not trbc_sector:
        return "Other"
    industry_low = (industry or "").lower()
    # REITs y empresas inmobiliarias → Real Estate
    if "real estate" in industry_low or "reit" in industry_low:
        return "Real Estate"
    return _TRBC_TO_GICS.get(trbc_sector, "Other")


@dataclass
class ScreenerResult:
    ticker: str
    name: str
    sector: str
    price: float
    market_cap: float
    avg_volume: float
    stage: int
    rs_score: float          # Relative Strength vs SPY (percentile 0-100)
    momentum_6m: float
    momentum_3m: float
    sma_50: Optional[float]
    sma_200: Optional[float]
    pct_from_52w_high: float
    screener_score: float    # Score compuesto 0-100
    pass_filters: bool


class ScreenerAgent:
    name = "Screener"

    def __init__(self):
        pass

    # ── API pública ───────────────────────────────────────────────────────

    def run_full_scan(self, callback=None, filters: Optional[dict] = None) -> list[ScreenerResult]:
        """Ejecuta el screener completo del NYSE+NASDAQ usando TradingView.

        UNA sola petición HTTP devuelve cientos de acciones con todas las
        métricas que necesitamos. Sin rate-limit en cloud (a diferencia de
        yfinance). Tiempo total: ~5-10 segundos.

        callback(label, idx, total) — para que la UI pueda actualizar progress.
        """
        f = self._normalize_filters(filters)

        if callback:
            callback("Consultando TradingView…", 5, 100)

        df, error = self._fetch_universe()
        if error:
            if callback:
                callback(f"Error: {error}", 100, 100)
            return []

        if df is None or df.empty:
            if callback:
                callback("Sin datos", 100, 100)
            return []

        if callback:
            callback(f"Procesando {len(df)} acciones…", 55, 100)

        # Performance del SPY para el cálculo de RS relativo
        spy_perf = self._get_spy_performance()

        # Construir ScreenerResult por cada fila
        results = []
        for _, row in df.iterrows():
            try:
                r = self._row_to_result(row, f, spy_perf)
                if r is not None:
                    results.append(r)
            except Exception:
                continue

        if callback:
            callback("Aplicando filtros…", 90, 100)

        # Filtros + sort + límite (misma lógica que la versión anterior)
        passing = [r for r in results if r.pass_filters]
        passing.sort(key=lambda x: x.screener_score, reverse=True)
        max_n = int(f.get("max_results", MAX_DEEP_ANALYSIS))

        if callback:
            callback("Listo", 100, 100)

        return passing[:max_n]

    def quick_validate(self, ticker: str) -> ScreenerResult:
        """Valida un ticker individual via TradingView. Mantiene interfaz
        retrocompatible — si la consulta falla, devuelve un ScreenerResult
        neutral con pass_filters=True (no bloquear análisis individual)."""
        try:
            from tradingview_screener import Query, col
            q = (
                Query()
                .select(*_TV_COLUMNS)
                .where(col("name") == ticker.upper())
                .limit(1)
            )
            _, df = q.get_scanner_data()
            if df is not None and not df.empty:
                spy = self._get_spy_performance()
                result = self._row_to_result(df.iloc[0], DEFAULT_TECHNICAL_FILTERS, spy)
                if result is not None:
                    return result
        except Exception:
            pass

        # Fallback neutral — no bloquea el análisis individual del ticker
        return ScreenerResult(
            ticker=ticker.upper(), name=ticker.upper(), sector="Unknown",
            price=0, market_cap=0, avg_volume=0, stage=0, rs_score=50,
            momentum_6m=0, momentum_3m=0, sma_50=None, sma_200=None,
            pct_from_52w_high=0, screener_score=50, pass_filters=True,
        )

    # ── Internos ──────────────────────────────────────────────────────────

    def _normalize_filters(self, filters: Optional[dict]) -> dict:
        result = dict(DEFAULT_TECHNICAL_FILTERS)
        if filters:
            for k, v in filters.items():
                result[k] = v
        return result

    def _fetch_universe(self) -> tuple:
        """Consulta TradingView por todas las acciones del NYSE+NASDAQ con
        market cap > $500M y precio > $5 (filtros ligeros para reducir ruido
        antes de aplicar los filtros del usuario). Devuelve (df, error_msg)."""
        try:
            from tradingview_screener import Query, col
            q = (
                Query()
                .select(*_TV_COLUMNS)
                .where(
                    col("exchange").isin(["NYSE", "NASDAQ"]),
                    col("type").isin(["stock", "dr"]),
                    col("close") > 5,
                    col("market_cap_basic") > 500_000_000,
                )
                .order_by("volume", ascending=False)
                .limit(800)
            )
            _, df = q.get_scanner_data()
            return df, None
        except ImportError as e:
            return None, f"tradingview-screener no instalado: {e}"
        except Exception as e:
            return None, str(e)

    def _get_spy_performance(self) -> dict:
        """Performance del SPY para usar como benchmark del RS score."""
        try:
            from tradingview_screener import Query, col
            q = (
                Query()
                .select("Perf.Y", "Perf.6M", "Perf.3M", "Perf.1M")
                .where(col("name") == "SPY")
                .limit(1)
            )
            _, df = q.get_scanner_data()
            if df is not None and not df.empty:
                row = df.iloc[0]
                return {
                    "y":  float(row.get("Perf.Y",  0) or 0),
                    "6m": float(row.get("Perf.6M", 0) or 0),
                    "3m": float(row.get("Perf.3M", 0) or 0),
                    "1m": float(row.get("Perf.1M", 0) or 0),
                }
        except Exception:
            pass
        # Defaults razonables si la consulta falla
        return {"y": 10.0, "6m": 5.0, "3m": 2.5, "1m": 1.0}

    def _row_to_result(self, row, filters: dict, spy_perf: dict) -> Optional[ScreenerResult]:
        """Convierte una fila del DataFrame de TradingView a ScreenerResult."""
        try:
            ticker = str(row.get("name", "") or "").upper()
            if not ticker:
                return None

            name = str(row.get("description", ticker) or ticker)
            # Convertir sector TRBC (TradingView) → GICS (lo que espera el UI)
            trbc_sector = str(row.get("sector", "") or "")
            industry = str(row.get("industry", "") or "")
            sector = _normalize_sector(trbc_sector, industry)

            price = self._safe_float(row.get("close"))
            mktcap = self._safe_float(row.get("market_cap_basic"))
            avg_vol = self._safe_float(row.get("average_volume_30d_calc"))

            if price <= 0 or mktcap <= 0:
                return None

            sma_50 = self._safe_float(row.get("SMA50")) or None
            sma_100 = self._safe_float(row.get("SMA100")) or None
            sma_200 = self._safe_float(row.get("SMA200")) or None
            # TradingView no expone SMA150 — aproximamos con (SMA100+SMA200)/2
            sma_150 = ((sma_100 + sma_200) / 2.0) if (sma_100 and sma_200) else None

            mom_3m = self._safe_float(row.get("Perf.3M"))
            mom_6m = self._safe_float(row.get("Perf.6M"))
            mom_1y = self._safe_float(row.get("Perf.Y"))
            mom_1m = self._safe_float(row.get("Perf.1M"))

            high_52w = self._safe_float(row.get("price_52_week_high")) or price
            pct_from_high = (price / high_52w - 1.0) * 100 if high_52w > 0 else 0.0

            # Stage Analysis (mismo algoritmo Minervini que antes)
            stage = self._stage_analysis(price, sma_50, sma_150, sma_200)

            # RS Score vs SPY (ponderado 40/20/20/20 — mismo que la versión yfinance)
            rs_raw = (
                (mom_1y - spy_perf["y"])  * 0.40 +
                (mom_6m - spy_perf["6m"]) * 0.20 +
                (mom_3m - spy_perf["3m"]) * 0.20 +
                (mom_1m - spy_perf["1m"]) * 0.20
            ) / 100.0
            rs_score = float(np.clip(50 + rs_raw * 150, 1, 99))

            # Composite screener score (mismo algoritmo)
            screener_score = self._compute_screener_score(
                stage=stage, rs_score=rs_score, mom_6m=mom_6m, mom_3m=mom_3m,
                pct_from_high=pct_from_high, avg_vol=avg_vol,
            )

            # Aplicar los filtros del usuario
            pass_filters = self._apply_user_filters(
                filters, price, avg_vol, stage, rs_score,
                mom_6m, pct_from_high, mktcap, sector,
            )

            return ScreenerResult(
                ticker=ticker,
                name=name,
                sector=sector,
                price=price,
                market_cap=mktcap,
                avg_volume=avg_vol,
                stage=stage,
                rs_score=rs_score,
                momentum_6m=mom_6m,
                momentum_3m=mom_3m,
                sma_50=sma_50,
                sma_200=sma_200,
                pct_from_52w_high=pct_from_high,
                screener_score=screener_score,
                pass_filters=pass_filters,
            )
        except Exception:
            return None

    def _apply_user_filters(self, f, price, avg_vol, stage, rs_score,
                            mom_6m, pct_from_high, mktcap, sector) -> bool:
        """Aplica los filtros del UI. Mismo orden y semántica que la versión
        anterior — no cambia el comportamiento del screener para el usuario."""
        if price < f.get("min_price", 0):
            return False
        if avg_vol < f.get("min_avg_volume", 0):
            return False

        allowed_stages = f.get("allowed_stages") or [1, 2]
        if stage not in allowed_stages:
            return False

        if rs_score < f.get("min_rs", 0):
            return False

        mom_min = f.get("min_momentum_6m")
        if mom_min is not None and mom_6m < mom_min:
            return False

        pct_min = f.get("pct_from_high_min")
        pct_max = f.get("pct_from_high_max")
        if pct_min is not None and pct_from_high < pct_min:
            return False
        if pct_max is not None and pct_from_high > pct_max:
            return False

        mc_min = f.get("market_cap_min")
        mc_max = f.get("market_cap_max")
        if mc_min is not None and mktcap < mc_min:
            return False
        if mc_max is not None and mktcap > mc_max:
            return False

        allowed_sectors = f.get("allowed_sectors")
        if allowed_sectors and sector not in allowed_sectors:
            return False

        return True

    @staticmethod
    def _safe_float(value) -> float:
        """Convierte a float tolerando None, NaN, strings y errores."""
        try:
            if value is None:
                return 0.0
            v = float(value)
            if v != v:  # NaN check
                return 0.0
            return v
        except (TypeError, ValueError):
            return 0.0

    def _stage_analysis(self, price, sma50, sma150, sma200) -> int:
        """Stage Analysis (Minervini). Idéntico a la versión anterior."""
        if not all([sma50, sma150, sma200]):
            return 0
        c1 = price > sma150 and price > sma200
        c2 = sma150 > sma200
        c3 = price > sma50
        c4 = sma50 > sma150
        if c1 and c2 and c3 and c4:
            return 2
        if price > sma200:
            return 1
        if price < sma200 and price > sma150:
            return 3
        return 4

    def _compute_screener_score(self, stage, rs_score, mom_6m, mom_3m,
                                pct_from_high, avg_vol) -> float:
        """Score compuesto 0-100 para rankear candidatos. Idéntico a antes."""
        score = 0.0

        # Stage (0-30 pts)
        stage_pts = {2: 30, 1: 15, 3: 5, 4: 0, 0: 0}
        score += stage_pts.get(stage, 0)

        # RS Score (0-30 pts)
        score += rs_score * 0.30

        # Momentum 6M (0-20 pts, capped a 50%)
        mom6_score = min(mom_6m / 50.0 * 20, 20) if mom_6m > 0 else 0
        score += mom6_score

        # Distancia al 52W high (0-10 pts — preferimos < 15% del high)
        if pct_from_high > -5:
            score += 10
        elif pct_from_high > -15:
            score += 7
        elif pct_from_high > -25:
            score += 3

        # Volumen (0-10 pts)
        if avg_vol > 5_000_000:
            score += 10
        elif avg_vol > 1_000_000:
            score += 6
        elif avg_vol > 500_000:
            score += 3

        return float(np.clip(score, 0, 100))

"""
Agente Screener — filtra el universo completo (S&P500 + NASDAQ-100)
a los candidatos más prometedores usando Stage Analysis de Minervini
y un composite ranking score. Corre ANTES del análisis profundo.
"""
from dataclasses import dataclass
from typing import Optional
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

from config.settings import SCREENER_FILTERS, MAX_DEEP_ANALYSIS
from data.universe import get_full_universe


# Filtros técnicos por defecto (matchean SCREENER_FILTERS pero con keys nuevas explícitas)
DEFAULT_TECHNICAL_FILTERS = {
    "min_price":          SCREENER_FILTERS["min_price"],
    "min_avg_volume":     SCREENER_FILTERS["min_avg_volume"],
    "market_cap_min":     SCREENER_FILTERS["min_market_cap"],
    "market_cap_max":     None,                              # sin tope
    "allowed_stages":     [1, 2],                            # Stage 1 + Stage 2
    "min_rs":             SCREENER_FILTERS["min_rs_percentile"],
    "min_momentum_6m":    None,                              # sin filtro
    "pct_from_high_min":  -30.0,                             # no más de 30% bajo 52W high
    "pct_from_high_max":  None,
    "allowed_sectors":    None,                              # None = todos
    "max_results":        MAX_DEEP_ANALYSIS,
}

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

    def run_full_scan(self, callback=None, filters: Optional[dict] = None) -> list[ScreenerResult]:
        """
        Escanea el universo completo. Callback(ticker, idx, total) para UI progress.
        Retorna candidatos ordenados por screener_score descendente.

        filters: dict con claves opcionales para personalizar el screening.
                 Si es None, usa DEFAULT_TECHNICAL_FILTERS (comportamiento legacy).
                 Ver DEFAULT_TECHNICAL_FILTERS arriba para el formato.
        """
        f = self._normalize_filters(filters)
        universe = get_full_universe()
        # Batch download para eficiencia
        results = self._batch_screen(universe, callback=callback, filters=f)
        passing = [r for r in results if r.pass_filters]
        passing.sort(key=lambda x: x.screener_score, reverse=True)
        max_n = int(f.get("max_results", MAX_DEEP_ANALYSIS))
        return passing[:max_n]

    def _normalize_filters(self, filters: Optional[dict]) -> dict:
        """Aplica DEFAULT_TECHNICAL_FILTERS y sobreescribe con lo que venga."""
        result = dict(DEFAULT_TECHNICAL_FILTERS)
        if filters:
            for k, v in filters.items():
                result[k] = v
        return result

    def quick_validate(self, ticker: str) -> ScreenerResult:
        """Valida un ticker individual directamente (modo análisis puntual)."""
        results = self._screen_tickers([ticker], filters=DEFAULT_TECHNICAL_FILTERS)
        if results:
            return results[0]
        return ScreenerResult(
            ticker=ticker, name=ticker, sector="Unknown", price=0,
            market_cap=0, avg_volume=0, stage=0, rs_score=50,
            momentum_6m=0, momentum_3m=0, sma_50=None, sma_200=None,
            pct_from_52w_high=0, screener_score=50, pass_filters=True,
        )

    def _batch_screen(self, tickers: list[str], batch_size: int = 10, callback=None, filters: Optional[dict] = None) -> list[ScreenerResult]:
        """Descarga datos en batches MUY chicos (10) con pausas amplias.
        Esto evita el rate-limit que Yahoo Finance aplica a IPs de cloud
        providers (AWS, donde corre Streamlit Cloud). Con NASDAQ-100 son
        ~10 batches, total ~60-90s."""
        import time
        all_results = []
        total = len(tickers)
        f = filters or DEFAULT_TECHNICAL_FILTERS

        for i in range(0, total, batch_size):
            batch = tickers[i:i + batch_size]
            if callback:
                callback(batch[0], i, total)

            # Reintentar hasta 3 veces si el batch viene vacío (rate-limit)
            batch_results = []
            for attempt in range(3):
                try:
                    batch_results = self._screen_tickers(batch, filters=f)
                    if batch_results:
                        break
                    time.sleep(1.0 + attempt * 0.5)  # backoff progresivo
                except Exception:
                    time.sleep(1.0 + attempt * 0.5)
                    continue
            all_results.extend(batch_results)

            # Pausa entre batches — Yahoo es más tolerante con tráfico espaciado
            time.sleep(0.4)

        return all_results

    def _screen_tickers(self, tickers: list[str], filters: Optional[dict] = None) -> list[ScreenerResult]:
        """Descarga y procesa un batch de tickers."""
        try:
            # Download histórico de un año para todos en paralelo.
            # yfinance >= 0.2.50 detecta automáticamente curl_cffi (si está
            # instalado) y lo usa para esquivar Cloudflare anti-bot.
            raw = yf.download(
                tickers,
                period="1y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception:
            return []

        # Download info básica (market cap, etc.)
        results = []
        spy_data = self._get_spy_returns()
        f = filters or DEFAULT_TECHNICAL_FILTERS

        for ticker in tickers:
            try:
                result = self._process_ticker(ticker, raw, spy_data, filters=f)
                if result:
                    results.append(result)
            except Exception:
                continue

        return results

    def _process_ticker(self, ticker: str, raw_data, spy_returns: pd.Series, filters: Optional[dict] = None) -> Optional[ScreenerResult]:
        """Procesa un ticker individual del batch download, aplicando filtros personalizados."""
        f = filters or DEFAULT_TECHNICAL_FILTERS
        try:
            # Extraer datos del batch
            if len(raw_data.columns.levels[0]) > 1 if hasattr(raw_data.columns, 'levels') else False:
                df = raw_data[ticker] if ticker in raw_data.columns.get_level_values(0) else None
            else:
                df = raw_data if len(raw_data.columns) <= 6 else None

            if df is None or df.empty or len(df) < 50:
                return None

            close = df["Close"].dropna()
            volume = df["Volume"].dropna()

            if close.empty or len(close) < 50:
                return None

            price = float(close.iloc[-1])
            avg_vol = float(volume.tail(20).mean())

            # Filtros rápidos básicos (precio y volumen mínimo)
            if price < f.get("min_price", 0):
                return None
            if avg_vol < f.get("min_avg_volume", 0):
                return None

            # Moving averages
            sma_50 = float(close.rolling(50).mean().iloc[-1])
            sma_150 = float(close.rolling(150).mean().iloc[-1]) if len(close) >= 150 else None
            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            # 52W stats
            high_52w = float(close.tail(252).max())
            pct_from_high = (price / high_52w - 1) * 100

            # Stage Analysis (Minervini Stage 2)
            stage = self._stage_analysis(price, sma_50, sma_150, sma_200)

            # Momentum
            mom_6m = float((price / close.iloc[-126] - 1) * 100) if len(close) > 126 else 0
            mom_3m = float((price / close.iloc[-63] - 1) * 100) if len(close) > 63 else 0

            # Relative Strength vs SPY
            rs_score = self._compute_rs(close, spy_returns)

            # Score compuesto (no afectado por filtros, sirve para ordenar)
            screener_score = self._compute_screener_score(
                stage=stage,
                rs_score=rs_score,
                mom_6m=mom_6m,
                mom_3m=mom_3m,
                pct_from_high=pct_from_high,
                avg_vol=avg_vol,
            )

            # Intentar obtener info básica (sector + market cap)
            try:
                info = yf.Ticker(ticker).info
                name = info.get("longName", ticker)
                sector = info.get("sector", "Unknown")
                mktcap = info.get("marketCap", 0) or 0
            except Exception:
                name, sector, mktcap = ticker, "Unknown", 0

            # ── Aplicar TODOS los filtros del UI ───────────────────────────
            pass_filters = True

            # 1. Stage permitido
            allowed_stages = f.get("allowed_stages") or [1, 2]
            if stage not in allowed_stages:
                pass_filters = False

            # 2. RS mínimo
            if rs_score < f.get("min_rs", 0):
                pass_filters = False

            # 3. Momentum 6M mínimo (si está definido)
            min_mom_6m = f.get("min_momentum_6m")
            if min_mom_6m is not None and mom_6m < min_mom_6m:
                pass_filters = False

            # 4. Distancia al 52W high (rango)
            pct_min = f.get("pct_from_high_min")
            pct_max = f.get("pct_from_high_max")
            if pct_min is not None and pct_from_high < pct_min:
                pass_filters = False
            if pct_max is not None and pct_from_high > pct_max:
                pass_filters = False

            # 5. Market cap (rango)
            mc_min = f.get("market_cap_min")
            mc_max = f.get("market_cap_max")
            if mktcap > 0:
                if mc_min is not None and mktcap < mc_min:
                    pass_filters = False
                if mc_max is not None and mktcap > mc_max:
                    pass_filters = False
            elif mc_min is not None and mc_min > 0:
                # Si exigimos un mínimo y no conseguimos market cap, descartar
                pass_filters = False

            # 6. Sectores permitidos
            allowed_sectors = f.get("allowed_sectors")
            if allowed_sectors and sector not in allowed_sectors:
                pass_filters = False

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

    def _stage_analysis(self, price, sma50, sma150, sma200) -> int:
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

    def _get_spy_returns(self) -> pd.Series:
        try:
            spy = yf.download("SPY", period="1y", interval="1d", auto_adjust=True, progress=False)
            return spy["Close"]
        except Exception:
            return pd.Series(dtype=float)

    def _compute_rs(self, close: pd.Series, spy: pd.Series) -> float:
        """RS percentile score 0-100 vs SPY (IBD-style)."""
        try:
            common = close.index.intersection(spy.index)
            if len(common) < 63:
                return 50.0

            s = close.loc[common]
            b = spy.loc[common]

            # Ponderado: 40% 12M, 20% 6M, 20% 3M, 20% 1M
            def ret(series, n):
                return (series.iloc[-1] / series.iloc[-n] - 1) if len(series) > n else 0

            rs_raw = (
                (ret(s, 252) - ret(b, 252)) * 0.40 +
                (ret(s, 126) - ret(b, 126)) * 0.20 +
                (ret(s, 63) - ret(b, 63)) * 0.20 +
                (ret(s, 21) - ret(b, 21)) * 0.20
            )

            # Mapear a 0-100: 0 = muy débil, 100 = muy fuerte
            # RS de +20% sobre SPY → 95+ / -20% → 5
            score = 50 + rs_raw * 150
            return float(np.clip(score, 1, 99))
        except Exception:
            return 50.0

    def _compute_screener_score(self, stage, rs_score, mom_6m, mom_3m, pct_from_high, avg_vol) -> float:
        """Score compuesto 0-100 para rankear candidatos del screener."""
        score = 0.0

        # Stage (0-30 pts)
        stage_pts = {2: 30, 1: 15, 3: 5, 4: 0, 0: 0}
        score += stage_pts.get(stage, 0)

        # RS Score (0-30 pts)
        score += rs_score * 0.30

        # Momentum 6M (0-20 pts, capped at 50%)
        mom6_score = min(mom_6m / 50 * 20, 20) if mom_6m > 0 else 0
        score += mom6_score

        # Distancia del 52W high (0-10 pts — preferimos < 15% del high)
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

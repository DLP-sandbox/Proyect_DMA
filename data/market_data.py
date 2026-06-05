"""
Capa unificada de datos de mercado. Usa yfinance como fuente primaria
con caché local en JSON para minimizar llamadas a la API.
"""
import json
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import ta as ta_lib
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


# ── Helpers de caché ──────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _cache_valid(path: Path, ttl_hours: float = 4) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < ttl_hours * 3600


def _load_cache(key: str, ttl_hours: float = 4) -> Optional[dict]:
    p = _cache_path(key)
    if _cache_valid(p, ttl_hours):
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


# TTLs por tipo de dato — calibrados para máxima frescura temporal
TTL_PRICE_DAILY  = 1.0      # 1 hora — precios diarios
TTL_COMPANY_INFO = 4.0      # 4 horas — info corporativa
TTL_FINANCIALS   = 24.0     # 24 horas — fundamentales (quarterly)
TTL_EARNINGS     = 2.0      # 2 horas — fechas y resultados de earnings
TTL_NEWS         = 0.5      # 30 minutos — noticias deben ser frescas
TTL_HOLDERS      = 12.0     # 12 horas — institucionales/insiders
TTL_MACRO        = 1.0      # 1 hora — indicadores macro
TTL_RS           = 1.0      # 1 hora — relative strength
TTL_SNAPSHOT     = 0.05     # 3 minutos — precios en vivo
TTL_LIVE_PRICE   = 0.0167   # 60 segundos — precio actual en vivo de un solo ticker


def _save_cache(key: str, data: dict) -> None:
    try:
        _cache_path(key).write_text(json.dumps(data, default=str))
    except Exception:
        pass


# ── Datos de precio ───────────────────────────────────────────────────────

def get_price_history(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """OHLCV diario o semanal para análisis técnico."""
    key = f"price_{ticker}_{period}_{interval}"
    cached = _load_cache(key, ttl_hours=TTL_PRICE_DAILY)
    if cached:
        df = pd.DataFrame(cached)
        df.index = pd.to_datetime(df.index)
        return df

    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        return df

    _save_cache(key, df.to_dict())
    return df


def get_weekly_history(ticker: str, period: str = "3y") -> pd.DataFrame:
    return get_price_history(ticker, period=period, interval="1wk")


# ── Precio en vivo (siempre fresco — TTL 60 segundos) ────────────────────

def get_live_price(ticker: str) -> Optional[float]:
    """Obtiene el precio actual de un ticker, cacheado solo 60 segundos.
    Es ligero y rápido — usa fast_info que no descarga el JSON completo."""
    key = f"liveprice_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_LIVE_PRICE)
    if cached:
        return cached.get("price")

    try:
        stock = yf.Ticker(ticker)
        # fast_info es mucho más rápido que info — solo trae datos esenciales
        try:
            price = float(stock.fast_info.get("lastPrice") or stock.fast_info.get("last_price") or 0)
        except Exception:
            price = 0.0

        if not price:
            # Fallback: descargar histórico de 1 día
            df = stock.history(period="1d")
            if not df.empty:
                price = float(df["Close"].iloc[-1])

        if price > 0:
            _save_cache(key, {"price": price})
            return price
    except Exception:
        pass
    return None


# ── Información de la empresa ─────────────────────────────────────────────

def get_company_info(ticker: str) -> dict:
    key = f"info_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_COMPANY_INFO)
    if cached:
        # SIEMPRE refrescar el precio actual del cache — TTL 60s
        live = get_live_price(ticker)
        if live:
            cached["current_price"] = live
        return cached

    stock = yf.Ticker(ticker)
    try:
        info = stock.info or {}
    except Exception:
        info = {}

    result = {
        "name":            info.get("longName", ticker),
        "sector":          info.get("sector", "Unknown"),
        "industry":        info.get("industry", "Unknown"),
        "country":         info.get("country", "US"),
        "market_cap":      info.get("marketCap", 0),
        "employees":       info.get("fullTimeEmployees", 0),
        "description":     info.get("longBusinessSummary", ""),
        "website":         info.get("website", ""),
        "current_price":   info.get("currentPrice") or info.get("regularMarketPrice", 0),
        "52w_high":        info.get("fiftyTwoWeekHigh", 0),
        "52w_low":         info.get("fiftyTwoWeekLow", 0),
        "avg_volume":      info.get("averageVolume", 0),
        "shares_outstanding": info.get("sharesOutstanding", 0),
        "float_shares":    info.get("floatShares", 0),
        "short_ratio":     info.get("shortRatio", 0),
        "short_percent":   info.get("shortPercentOfFloat", 0),
        "beta":            info.get("beta", 1.0),
        "pe_ratio":        info.get("trailingPE", None),
        "forward_pe":      info.get("forwardPE", None),
        "ps_ratio":        info.get("priceToSalesTrailing12Months", None),
        "pb_ratio":        info.get("priceToBook", None),
        "ev_ebitda":       info.get("enterpriseToEbitda", None),
        "peg_ratio":       info.get("pegRatio", None),
        "dividend_yield":  info.get("dividendYield", 0),
        "target_price":    info.get("targetMeanPrice", 0),
        "analyst_rating":  info.get("recommendationKey", ""),
        "earnings_date":   str(info.get("earningsTimestamp", "")),
        # ── Métricas fundamentales DIRECTAS de Yahoo Finance ──────────────────
        # Fuente de verdad oficial — coinciden 1:1 con lo que muestra la web de YF
        "profit_margin":       info.get("profitMargins"),                  # decimal, ej: 0.699
        "operating_margin_yf": info.get("operatingMargins"),               # decimal, ej: 0.699
        "gross_margin_yf":     info.get("grossMargins"),                   # decimal, ej: 0.699
        "roe_yf":              info.get("returnOnEquity"),                 # decimal, ej: 0.22
        "roa_yf":              info.get("returnOnAssets"),                 # decimal
        "debt_equity_yf":      info.get("debtToEquity"),                   # ratio tal como muestra YF
        "revenue_ttm":         info.get("totalRevenue"),                   # valor absoluto TTM
        "ebitda_yf":           info.get("ebitda"),                         # valor absoluto
        "revenue_growth_yf":   info.get("revenueGrowth"),                  # decimal YoY directo
        "earnings_growth_yf":  info.get("earningsGrowth"),                 # decimal YoY directo
        "current_ratio_yf":    info.get("currentRatio"),                   # ratio
        "quick_ratio_yf":      info.get("quickRatio"),                     # ratio
        "fcf_yf":              info.get("freeCashflow"),                   # valor absoluto TTM
        "ocf_yf":              info.get("operatingCashflow"),              # valor absoluto TTM
        "total_cash_yf":       info.get("totalCash"),                      # valor absoluto
        "total_debt_yf":       info.get("totalDebt"),                      # valor absoluto
        "book_value_yf":       info.get("bookValue"),                      # por acción
        "enterprise_value_yf": info.get("enterpriseValue"),                # valor absoluto
        "ev_revenue_yf":       info.get("enterpriseToRevenue"),            # múltiplo
        "target_high_yf":      info.get("targetHighPrice"),
        "target_low_yf":       info.get("targetLowPrice"),
        "target_median_yf":    info.get("targetMedianPrice"),
        "num_analysts_yf":     info.get("numberOfAnalystOpinions"),
    }
    _save_cache(key, result)

    # Sobrescribir con precio en vivo si está disponible (más fresco)
    live = get_live_price(ticker)
    if live:
        result["current_price"] = live
    return result


# ── Métricas financieras ───────────────────────────────────────────────────

def get_financials(ticker: str) -> dict:
    key = f"financials_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_FINANCIALS)
    if cached:
        return cached

    stock = yf.Ticker(ticker)
    result = {}

    try:
        # Income Statement
        inc = stock.income_stmt
        if inc is not None and not inc.empty:
            cols = inc.columns[:4]  # últimos 4 años
            result["revenue"] = [float(inc.loc["Total Revenue", c]) if "Total Revenue" in inc.index else None for c in cols]
            result["gross_profit"] = [float(inc.loc["Gross Profit", c]) if "Gross Profit" in inc.index else None for c in cols]
            result["operating_income"] = [float(inc.loc["Operating Income", c]) if "Operating Income" in inc.index else None for c in cols]
            result["net_income"] = [float(inc.loc["Net Income", c]) if "Net Income" in inc.index else None for c in cols]
            result["ebitda"] = [float(inc.loc["EBITDA", c]) if "EBITDA" in inc.index else None for c in cols]
            result["fiscal_years"] = [str(c.year) for c in cols]
    except Exception:
        pass

    try:
        # Balance Sheet
        bal = stock.balance_sheet
        if bal is not None and not bal.empty:
            cols = bal.columns[:2]
            result["total_debt"] = float(bal.loc["Total Debt", cols[0]]) if "Total Debt" in bal.index else None
            result["cash"] = float(bal.loc["Cash And Cash Equivalents", cols[0]]) if "Cash And Cash Equivalents" in bal.index else None
            result["total_assets"] = float(bal.loc["Total Assets", cols[0]]) if "Total Assets" in bal.index else None
            result["total_equity"] = float(bal.loc["Stockholders Equity", cols[0]]) if "Stockholders Equity" in bal.index else None
            result["current_assets"] = float(bal.loc["Current Assets", cols[0]]) if "Current Assets" in bal.index else None
            result["current_liabilities"] = float(bal.loc["Current Liabilities", cols[0]]) if "Current Liabilities" in bal.index else None
    except Exception:
        pass

    try:
        # Cash Flow
        cf = stock.cashflow
        if cf is not None and not cf.empty:
            cols = cf.columns[:4]
            result["free_cash_flow"] = [float(cf.loc["Free Cash Flow", c]) if "Free Cash Flow" in cf.index else None for c in cols]
            result["operating_cash_flow"] = [float(cf.loc["Operating Cash Flow", c]) if "Operating Cash Flow" in cf.index else None for c in cols]
            result["capex"] = [float(cf.loc["Capital Expenditure", c]) if "Capital Expenditure" in cf.index else None for c in cols]
    except Exception:
        pass

    try:
        # Quarterly earnings history
        eq = stock.earnings_history
        if eq is not None and not eq.empty:
            eq = eq.tail(8)
            result["earnings_history"] = {
                "dates": [str(d) for d in eq.index.tolist()],
                "eps_estimate": eq["epsEstimate"].tolist() if "epsEstimate" in eq.columns else [],
                "eps_actual": eq["epsActual"].tolist() if "epsActual" in eq.columns else [],
                "surprise_pct": eq["surprisePercent"].tolist() if "surprisePercent" in eq.columns else [],
            }
    except Exception:
        pass

    _save_cache(key, result)
    return result


# ── Ratios y calidad ───────────────────────────────────────────────────────

def compute_quality_ratios(info: dict, financials: dict) -> dict:
    """Calcula ROE, ROIC, márgenes, Piotroski F-Score aproximado."""
    ratios = {}

    mktcap = info.get("market_cap", 0)
    rev = financials.get("revenue", [None])
    gp = financials.get("gross_profit", [None])
    oi = financials.get("operating_income", [None])
    ni = financials.get("net_income", [None])
    fcf = financials.get("free_cash_flow", [None])
    equity = financials.get("total_equity")
    debt = financials.get("total_debt", 0) or 0
    cash = financials.get("cash", 0) or 0
    assets = financials.get("total_assets")

    def safe(lst, idx=0):
        try:
            v = lst[idx]
            return float(v) if v is not None else None
        except Exception:
            return None

    r0, r1 = safe(rev, 0), safe(rev, 1)
    # Revenue growth: preferir YF directo (TTM más actualizado que anual)
    rg_yf = info.get("revenue_growth_yf")
    if rg_yf is not None:
        ratios["revenue_growth_yoy"] = float(rg_yf) * 100
    elif r0 and r1 and r1 != 0:
        ratios["revenue_growth_yoy"] = (r0 - r1) / abs(r1) * 100
    else:
        ratios["revenue_growth_yoy"] = None

    # Márgenes: preferir YF directo (decimales → %) sobre cálculo manual
    gm_yf = info.get("gross_margin_yf")
    if gm_yf is not None:
        ratios["gross_margin"] = float(gm_yf) * 100
    elif r0 and safe(gp, 0):
        ratios["gross_margin"] = safe(gp, 0) / r0 * 100

    om_yf = info.get("operating_margin_yf")
    if om_yf is not None:
        ratios["operating_margin"] = float(om_yf) * 100
    elif r0 and safe(oi, 0):
        ratios["operating_margin"] = safe(oi, 0) / r0 * 100

    pm_yf = info.get("profit_margin")
    if pm_yf is not None:
        ratios["net_margin"] = float(pm_yf) * 100
    elif r0 and safe(ni, 0):
        ratios["net_margin"] = safe(ni, 0) / r0 * 100

    # Revenue growth 2Y CAGR
    r2 = safe(rev, 2)
    if r0 and r2 and r2 > 0:
        ratios["revenue_cagr_2y"] = ((r0 / r2) ** 0.5 - 1) * 100

    # EPS growth: preferir YF directo
    eg_yf = info.get("earnings_growth_yf")
    if eg_yf is not None:
        ratios["earnings_growth_yoy"] = float(eg_yf) * 100
    else:
        ni0, ni1 = safe(ni, 0), safe(ni, 1)
        if ni0 and ni1 and ni1 != 0:
            ratios["earnings_growth_yoy"] = (ni0 - ni1) / abs(ni1) * 100

    # ROE: preferir YF directo
    roe_yf = info.get("roe_yf")
    if roe_yf is not None:
        ratios["roe"] = float(roe_yf) * 100
    elif safe(ni, 0) and equity and equity != 0:
        ratios["roe"] = safe(ni, 0) / equity * 100

    # ROIC proxy
    invested_capital = (equity or 0) + debt - cash
    if safe(oi, 0) and invested_capital and invested_capital > 0:
        ratios["roic"] = safe(oi, 0) * (1 - 0.21) / invested_capital * 100

    # FCF Yield: preferir FCF TTM directo de YF
    fcf0 = safe(fcf, 0)
    fcf_yf = info.get("fcf_yf")
    if fcf_yf and mktcap and mktcap > 0:
        ratios["fcf_yield"] = float(fcf_yf) / mktcap * 100
    elif fcf0 and mktcap and mktcap > 0:
        ratios["fcf_yield"] = fcf0 / mktcap * 100

    # Current ratio: preferir YF directo
    cr_yf = info.get("current_ratio_yf")
    if cr_yf is not None:
        ratios["current_ratio"] = float(cr_yf)
    else:
        ca = financials.get("current_assets")
        cl = financials.get("current_liabilities")
        if ca and cl and cl > 0:
            ratios["current_ratio"] = ca / cl

    # Debt/Equity: preferir YF directo (coincide con lo que muestra Yahoo Finance)
    de_yf = info.get("debt_equity_yf")
    if de_yf is not None:
        ratios["debt_to_equity"] = float(de_yf)
    elif debt and equity and equity > 0:
        ratios["debt_to_equity"] = debt / equity

    # FCF growth
    fcf1 = safe(fcf, 1)
    if fcf0 and fcf1 and fcf1 != 0:
        ratios["fcf_growth_yoy"] = (fcf0 - fcf1) / abs(fcf1) * 100

    # EV/Revenue
    if mktcap and debt and cash and r0:
        ev = mktcap + debt - cash
        ratios["ev_revenue"] = ev / r0 if r0 > 0 else None

    return ratios


# ── Indicadores técnicos ───────────────────────────────────────────────────

def compute_technical_indicators(df: pd.DataFrame) -> dict:
    """Calcula todos los indicadores técnicos clave sobre datos OHLCV diarios."""
    if df is None or df.empty or len(df) < 50:
        return {}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    indicators = {}

    # Moving Averages
    for n in [20, 50, 150, 200]:
        ma = close.rolling(n).mean()
        indicators[f"sma_{n}"] = float(ma.iloc[-1]) if not ma.empty else None
        indicators[f"price_vs_sma{n}_pct"] = float((close.iloc[-1] / ma.iloc[-1] - 1) * 100) if ma.iloc[-1] else None

    # EMA
    for n in [8, 21]:
        ema = close.ewm(span=n).mean()
        indicators[f"ema_{n}"] = float(ema.iloc[-1])

    # RSI
    try:
        rsi = ta_lib.momentum.RSIIndicator(close, window=14).rsi()
        indicators["rsi_14"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    except Exception:
        pass

    # MACD
    try:
        macd_ind = ta_lib.trend.MACD(close)
        indicators["macd"]        = float(macd_ind.macd().iloc[-1])
        indicators["macd_signal"] = float(macd_ind.macd_signal().iloc[-1])
        indicators["macd_hist"]   = float(macd_ind.macd_diff().iloc[-1])
    except Exception:
        pass

    # Bollinger Bands
    try:
        bb = ta_lib.volatility.BollingerBands(close)
        indicators["bb_upper"] = float(bb.bollinger_hband().iloc[-1])
        indicators["bb_mid"]   = float(bb.bollinger_mavg().iloc[-1])
        indicators["bb_lower"] = float(bb.bollinger_lband().iloc[-1])
        upper = indicators["bb_upper"]
        lower = indicators["bb_lower"]
        mid   = indicators["bb_mid"]
        if mid and mid > 0:
            indicators["bb_width"] = float((upper - lower) / mid * 100)
    except Exception:
        pass

    # ATR (volatilidad)
    try:
        atr = ta_lib.volatility.AverageTrueRange(high, low, close).average_true_range()
        indicators["atr_14"] = float(atr.iloc[-1])
        indicators["atr_pct"] = float(atr.iloc[-1] / close.iloc[-1] * 100)
    except Exception:
        pass

    # OBV
    try:
        obv = ta_lib.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
        indicators["obv"] = float(obv.iloc[-1])
        obv_ma = obv.rolling(20).mean()
        indicators["obv_trend"] = "rising" if obv.iloc[-1] > obv_ma.iloc[-1] else "falling"
    except Exception:
        pass

    # Volumen relativo (hoy vs promedio 20d)
    vol_avg = volume.rolling(20).mean()
    indicators["rel_volume"] = float(volume.iloc[-1] / vol_avg.iloc[-1]) if vol_avg.iloc[-1] > 0 else 1.0

    # Price stats
    indicators["current_price"] = float(close.iloc[-1])
    indicators["52w_high"] = float(high.tail(252).max())
    indicators["52w_low"] = float(low.tail(252).min())
    indicators["pct_from_52w_high"] = float((close.iloc[-1] / high.tail(252).max() - 1) * 100)
    indicators["pct_from_52w_low"] = float((close.iloc[-1] / low.tail(252).min() - 1) * 100)

    # Stage Analysis (Minervini)
    indicators["stage"] = _compute_stage(close, indicators)

    # Momentum (6M, 3M, 1M returns)
    for n, label in [(126, "6m"), (63, "3m"), (21, "1m")]:
        if len(close) > n:
            ret = (close.iloc[-1] / close.iloc[-n] - 1) * 100
            indicators[f"return_{label}"] = float(ret)

    return indicators


def _compute_stage(close: pd.Series, ind: dict) -> int:
    """Stage Analysis estilo Minervini. Stage 2 = tendencia alcista ideal."""
    try:
        p = float(close.iloc[-1])
        sma50 = ind.get("sma_50")
        sma150 = ind.get("sma_150")
        sma200 = ind.get("sma_200")

        if not all([sma50, sma150, sma200]):
            return 0

        # Stage 2 criteria (ideal para comprar)
        c1 = p > sma150 and p > sma200
        c2 = sma150 > sma200
        c3 = p > sma50
        c4 = sma50 > sma150

        if c1 and c2 and c3 and c4:
            return 2
        elif p > sma200 and sma200 > 0:
            return 1  # acumulación
        elif p < sma200 and p > sma150:
            return 3  # distribución temprana
        else:
            return 4  # downtrend
    except Exception:
        return 0


# ── Relative Strength vs SPY ──────────────────────────────────────────────

def get_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "1y") -> dict:
    """RS Rating: performance relativa vs S&P500."""
    key = f"rs_{ticker}_{benchmark}_{period}"
    cached = _load_cache(key, ttl_hours=TTL_RS)
    if cached:
        return cached

    stock_data = get_price_history(ticker, period=period)
    spy_data = get_price_history(benchmark, period=period)

    result = {"rs_score": 50, "rs_6m": None, "rs_3m": None, "rs_1m": None}

    if stock_data.empty or spy_data.empty:
        return result

    # Alinear fechas
    common = stock_data.index.intersection(spy_data.index)
    if len(common) < 20:
        return result

    s = stock_data.loc[common, "Close"]
    spy = spy_data.loc[common, "Close"]

    for n, label in [(126, "rs_6m"), (63, "rs_3m"), (21, "rs_1m")]:
        if len(s) > n:
            s_ret = (s.iloc[-1] / s.iloc[-n] - 1)
            spy_ret = (spy.iloc[-1] / spy.iloc[-n] - 1)
            result[label] = float((s_ret - spy_ret) * 100)

    # RS Score compuesto (ponderado 40/20/20/20 para 12M/6M/3M/1M)
    r12 = (s.iloc[-1] / s.iloc[0] - 1) if len(s) > 200 else 0
    spy12 = (spy.iloc[-1] / spy.iloc[0] - 1)
    rs12 = r12 - spy12
    rs6 = (result.get("rs_6m") or 0) / 100
    rs3 = (result.get("rs_3m") or 0) / 100
    rs1 = (result.get("rs_1m") or 0) / 100

    composite = rs12 * 0.40 + rs6 * 0.20 + rs3 * 0.20 + rs1 * 0.20
    # Normalizar a 0-99
    result["rs_composite"] = float(composite)

    _save_cache(key, result)
    return result


# ── Holders e institucionales ──────────────────────────────────────────────

def get_holders_data(ticker: str) -> dict:
    key = f"holders_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_HOLDERS)
    if cached:
        return cached

    stock = yf.Ticker(ticker)
    result = {}

    try:
        inst = stock.institutional_holders
        if inst is not None and not inst.empty:
            result["top_institutions"] = inst.head(10).to_dict(orient="records")
            result["institutional_ownership_pct"] = float(inst["% Out"].sum()) if "% Out" in inst.columns else None
    except Exception:
        pass

    try:
        insiders = stock.insider_transactions
        if insiders is not None and not insiders.empty:
            recent = insiders.head(20)
            buys = recent[recent.get("Transaction", recent.get("Shares", pd.Series(dtype=str))).astype(str).str.contains("Buy|Purchase", case=False, na=False)]
            result["recent_insider_buys"] = len(buys)
            result["insider_transactions"] = recent[["Date", "Insider", "Position", "Shares", "Value"]].to_dict(orient="records") if all(c in recent.columns for c in ["Date", "Insider", "Position", "Shares", "Value"]) else []
    except Exception:
        pass

    try:
        mh = stock.major_holders
        if mh is not None and not mh.empty:
            result["major_holders_raw"] = mh.to_dict()
    except Exception:
        pass

    _save_cache(key, result)
    return result


# ── Noticias ───────────────────────────────────────────────────────────────

def get_news(ticker: str, max_items: int = 15) -> list[dict]:
    """Noticias ordenadas por fecha descendente (más recientes primero)
    con campo 'age_hours' calculado para que los agentes sepan qué tan reciente es."""
    key = f"news_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_NEWS)
    if cached:
        return cached

    stock = yf.Ticker(ticker)
    result = []
    now = datetime.now()

    try:
        news = stock.news or []
        for item in news:
            try:
                # yfinance puede devolver el formato anidado nuevo o el plano antiguo
                content = item.get("content", item)
                title = content.get("title", item.get("title", ""))
                publisher = (content.get("provider", {}).get("displayName")
                             if isinstance(content.get("provider"), dict)
                             else item.get("publisher", ""))
                link = (content.get("canonicalUrl", {}).get("url")
                        if isinstance(content.get("canonicalUrl"), dict)
                        else item.get("link", ""))

                ts = (item.get("providerPublishTime") or
                      content.get("pubDate") or
                      content.get("displayTime"))

                if isinstance(ts, (int, float)):
                    pub_dt = datetime.fromtimestamp(ts)
                elif isinstance(ts, str):
                    try:
                        pub_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pub_dt = now
                else:
                    pub_dt = now

                age_hours = (now - pub_dt).total_seconds() / 3600

                if title:
                    result.append({
                        "title":      title,
                        "publisher":  publisher or "",
                        "link":       link or "",
                        "date":       pub_dt.strftime("%Y-%m-%d %H:%M"),
                        "age_hours":  round(age_hours, 1),
                        "freshness":  ("🔥 HOY" if age_hours < 24 else
                                       "⚡ Esta semana" if age_hours < 168 else
                                       "📅 Antigua"),
                    })
            except Exception:
                continue

        # Ordenar por fecha desc (más recientes primero)
        result.sort(key=lambda x: x.get("age_hours", 9999))
        result = result[:max_items]
    except Exception:
        pass

    _save_cache(key, result)
    return result


# ── Macro Data (sin FRED key, usando yfinance) ────────────────────────────

def get_macro_data() -> dict:
    key = "macro_global"
    cached = _load_cache(key, ttl_hours=TTL_MACRO)
    if cached:
        return cached

    result = {}
    # Índices reales (no ETFs): ^GSPC = S&P 500 Index, ^IXIC = NASDAQ Composite, etc.
    tickers_map = {
        "sp500":  "^GSPC",      # S&P 500 Index (puntos del índice)
        "nasdaq": "^IXIC",      # NASDAQ Composite Index (puntos)
        "vix":    "^VIX",       # Volatility Index
        "dxy":    "DX-Y.NYB",   # US Dollar Index (NYSE)
        "tnx":    "^TNX",       # 10Y Treasury Yield (en %)
        "tyx":    "^TYX",       # 30Y Treasury Yield (en %)
        "irx":    "^IRX",       # 13-week T-bill (en %)
        "gold":   "GC=F",       # Gold Futures (precio onza troy)
        "oil":    "CL=F",       # Crude Oil WTI Futures
    }

    sector_etfs = {
        "XLK": "Technology",
        "XLV": "Healthcare",
        "XLF": "Financials",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLC": "Communication",
        "XLY": "Consumer Disc",
        "XLP": "Consumer Staples",
        "XLRE": "Real Estate",
        "XLB": "Materials",
        "XLU": "Utilities",
    }

    for key_name, sym in tickers_map.items():
        try:
            # Usar .history() en lugar de download() para evitar multi-index columns
            df = yf.Ticker(sym).history(period="3mo")
            if df.empty or "Close" not in df.columns:
                continue
            close = df["Close"].dropna()
            if close.empty:
                continue
            current = float(close.iloc[-1])
            chg_1m = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else None
            chg_3m = float((close.iloc[-1] / close.iloc[0] - 1) * 100) if len(close) > 1 else None
            result[key_name] = {
                "current":   current,
                "1m_change": chg_1m,
                "3m_change": chg_3m,
            }
        except Exception:
            pass

    # Sector performance (1 mes)
    # Rendimiento sectorial a 1 año (desde hace 365 días hasta hoy)
    sector_perf = {}
    for etf, name in sector_etfs.items():
        try:
            # Usar .history() (no .download) para evitar multi-index column bugs
            df = yf.Ticker(etf).history(period="1y")
            if df.empty or "Close" not in df.columns:
                continue
            close = df["Close"].dropna()
            if close.empty or len(close) < 2:
                continue
            ret = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
            sector_perf[name] = ret
        except Exception:
            pass

    result["sector_performance"] = sector_perf

    # Yield curve spread (10Y - 2Y)
    try:
        df2 = yf.download("^IRX", period="5d", interval="1d", auto_adjust=True, progress=False)
        df10 = result.get("tnx", {})
        if not df2.empty and df10:
            rate_2y = float(df2["Close"].iloc[-1]) / 100
            rate_10y = df10.get("current", 0) / 100
            result["yield_curve_spread"] = float((rate_10y - rate_2y) * 100)
    except Exception:
        pass

    _save_cache("macro_global", result)
    return result


# ── Snapshot rápido de tickers populares ──────────────────────────────────

POPULAR_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "GOOGL", "META", "AMZN", "AMD", "AVGO", "NFLX", "COIN", "PLTR"]


def get_live_snapshot(tickers: list[str] = None) -> dict:
    """Snapshot rápido de precio + cambio % diario para una lista de tickers.
    Cache de 5 minutos para no martillar yfinance."""
    if tickers is None:
        tickers = POPULAR_TICKERS

    key = f"snapshot_{'_'.join(sorted(tickers))[:80]}"
    cached = _load_cache(key, ttl_hours=TTL_SNAPSHOT)
    if cached:
        return cached

    result = {}
    try:
        data = yf.download(tickers, period="5d", interval="1d", auto_adjust=True,
                          progress=False, group_by="ticker", threads=True)
        for ticker in tickers:
            try:
                if len(tickers) > 1 and ticker in data.columns.get_level_values(0):
                    df = data[ticker].dropna()
                else:
                    df = data.dropna()
                if df.empty or len(df) < 2:
                    continue
                price = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                change_pct = (price - prev) / prev * 100 if prev > 0 else 0
                result[ticker] = {
                    "price": price,
                    "change_pct": change_pct,
                    "change_abs": price - prev,
                }
            except Exception:
                continue
    except Exception:
        pass

    if result:
        _save_cache(key, result)
    return result


# ── Análisis de earnings ───────────────────────────────────────────────────

def get_earnings_data(ticker: str) -> dict:
    """Earnings con días desde HOY al próximo reporte calculados explícitamente."""
    key = f"earnings_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_EARNINGS)
    if cached:
        return cached

    stock = yf.Ticker(ticker)
    result = {}
    now = pd.Timestamp.now()

    try:
        cal = stock.earnings_dates
        if cal is not None and not cal.empty:
            # Normalizar tz si existe
            if cal.index.tz is not None:
                cal.index = cal.index.tz_localize(None)

            upcoming = cal[cal.index > now].sort_index().head(3)
            past = cal[cal.index <= now].sort_index(ascending=False).head(8)

            if not upcoming.empty:
                next_date = upcoming.index[0]
                days_to_next = (next_date - now).days
                result["next_earnings"] = str(next_date.date())
                result["days_to_next_earnings"] = days_to_next
                result["next_earnings_proximity"] = (
                    "🔥 INMINENTE" if days_to_next <= 7 else
                    "⚡ PRÓXIMO" if days_to_next <= 30 else
                    "📅 LEJANO"
                )

                # Lista completa de upcoming
                result["upcoming_earnings"] = [
                    {"date": str(idx.date()), "days_from_today": (idx - now).days,
                     "eps_estimate": float(row.get("EPS Estimate", 0)) if pd.notna(row.get("EPS Estimate")) else None}
                    for idx, row in upcoming.iterrows()
                ]

            if not past.empty:
                surprises = []
                for idx, row in past.iterrows():
                    est = row.get("EPS Estimate")
                    act = row.get("Reported EPS")
                    if pd.notna(est) and pd.notna(act) and est != 0:
                        surp = float((act - est) / abs(est) * 100)
                        days_ago = (now - idx).days
                        surprises.append({
                            "date": str(idx.date()),
                            "days_ago": days_ago,
                            "estimate": float(est),
                            "actual": float(act),
                            "surprise_pct": surp,
                        })
                result["earnings_history"] = surprises
                if surprises:
                    result["avg_surprise"] = sum(s["surprise_pct"] for s in surprises) / len(surprises)
                    result["beat_count"] = sum(1 for s in surprises if s["surprise_pct"] > 0)
    except Exception:
        pass

    _save_cache(key, result)
    return result

"""
Capa unificada de datos de mercado. Usa yfinance como fuente primaria
con caché local en JSON para minimizar llamadas a la API.
"""
import json
import re
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import ta as ta_lib
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


# ── Constructor de yf.Ticker (envoltorio único) ───────────────────────────
# yfinance 1.x YA impersona a Chrome internamente vía curl_cffi, así que el
# `yf.Ticker(ticker)` pelado es lo correcto para IPs de datacenter (Render /
# Cloud). NO se le pasa una sesión curl_cffi externa: en yfinance 1.x eso
# CHOCA con su sesión interna y CUELGA el render de Streamlit (pantalla en
# blanco). Este envoltorio existe solo para tener un único punto de creación.
def _yt(ticker: str):
    return yf.Ticker(ticker)


# ── Validación de ticker (rápida, gratis — NO usa Anthropic) ──────────────

# Regex de caracteres permitidos en un ticker NYSE/NASDAQ.
# Acepta letras A-Z, dígitos 0-9 y guion `-` (ej: BRK-B, BF-B, AAPL, 8011).
_TICKER_PATTERN = re.compile(r"^[A-Z0-9\-]{1,10}$")


# ── Activos NO soportados (acciones individuales únicamente) ──────────────
# La app DLP analiza acciones individuales (stocks + ADRs del NYSE/NASDAQ).
# NO analiza ETFs, criptomonedas, futures, forex ni índices, porque la lógica
# de los agentes (fundamentales, técnico, futuro, etc.) asume una empresa
# subyacente con earnings, P/E, sector específico, etc. — cosas que no tienen
# los ETFs o las criptos. Si el usuario intenta uno de estos, mostramos un
# mensaje específico AHORA — antes de gastar créditos de Anthropic.

_ETF_TICKERS = frozenset([
    # Índices broad market
    "VOO", "SPY", "IVV", "VTI", "VXUS", "IWM", "DIA", "MDY", "RSP",
    # Tech / Nasdaq
    "QQQ", "QQQM", "XLK", "VGT", "FTEC", "SOXX", "SMH",
    # Sector SPDRs
    "XLE", "XLF", "XLI", "XLY", "XLP", "XLV", "XLU", "XLB", "XLRE", "XLC",
    # Bonds
    "TLT", "BND", "AGG", "HYG", "LQD", "SHY", "TIP", "IEF", "BIL", "VTEB",
    # Crypto ETFs (cotizan en NYSE/NASDAQ pero son ETFs, no acciones)
    "IBIT", "GBTC", "FBTC", "BITO", "ETHA", "ETHE", "BITQ", "BITX",
    # Commodities
    "GLD", "SLV", "USO", "UNG", "DBA", "DBC", "PDBC", "IAU", "GLDM",
    # International / Emerging Markets
    "VEA", "VWO", "EFA", "EEM", "IEFA", "IEMG", "VEU", "IXUS", "ACWI",
    # ARK
    "ARKK", "ARKG", "ARKW", "ARKQ", "ARKF", "ARKX",
    # Leveraged / Inverse
    "TQQQ", "SQQQ", "UPRO", "SPXU", "SOXL", "SOXS", "TMF", "TMV",
    "TNA", "TZA", "FAS", "FAZ", "UDOW", "SDOW",
    # Dividend / Value
    "VYM", "SCHD", "DVY", "NOBL", "VIG", "DGRO", "HDV", "SPHD",
    # Money market / Cash
    "BIL", "SGOV", "USFR",
])

_CRYPTO_TICKERS = frozenset([
    "BTC", "BITCOIN", "BTCUSD",
    "ETH", "ETHEREUM", "ETHUSD",
    "USDT", "USDC", "BNB", "XRP", "SOL", "ADA", "DOGE", "AVAX",
    "DOT", "MATIC", "LINK", "LTC", "BCH", "XLM", "TRX", "UNI",
    "ATOM", "ALGO", "FIL", "ETC", "NEAR", "APT", "ARB", "OP",
    "SHIB", "PEPE", "FLOKI", "WIF", "BONK",
])

_FUTURES_FOREX = frozenset([
    # Futures comunes (CME, COMEX)
    "ES", "NQ", "YM", "RTY", "GC", "CL", "SI", "NG", "ZC", "ZS",
    "ZW", "ZN", "ZB", "ZF", "BTC1", "MES", "MNQ", "MYM", "M2K",
    # Forex
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
    "NZDUSD", "EURJPY", "GBPJPY", "EURCHF", "DXY",
])


def validate_ticker(raw_input: str) -> Tuple[bool, str, str]:
    """Valida un ticker manual ANTES de lanzar el análisis.

    Hace 3 cosas:
      1. Limpia el input (trim espacios, mayúsculas, `.` → `-` para BRK.B).
      2. Verifica que solo contenga letras, dígitos y guion (regex).
      3. Confirma que existe en NYSE/NASDAQ vía TradingView (gratis, ~200ms).

    Retorna `(is_valid, clean_ticker, error_message)`:
      - `(True, "NVDA", "")` si todo OK.
      - `(False, "", "mensaje claro")` si hay error de chars o no existe.

    IMPORTANTE: NO usa Anthropic API. Si TradingView falla por cualquier
    razón (network, rate-limit), retorna `(True, clean, "")` para NO
    bloquear injustamente al usuario — el análisis después fallará gracefully
    si el ticker realmente no existe."""
    if not raw_input or not str(raw_input).strip():
        return False, "", "Por favor introduce un ticker para analizar."

    # 1. Limpieza: espacios fuera, mayúsculas, `.` → `-` (BRK.B → BRK-B)
    clean = str(raw_input).strip().upper().replace(".", "-")

    if not clean:
        return False, "", "Por favor introduce un ticker para analizar."

    # 2. Validación de caracteres (solo A-Z, 0-9, guion; máx 10 chars)
    if not _TICKER_PATTERN.match(clean):
        return False, "", (
            f"⚠️ El ticker **\"{str(raw_input).strip()}\"** contiene "
            f"caracteres inválidos. Solo se permiten letras (A-Z), dígitos "
            f"(0-9) y guion (-). Ejemplos válidos: NVDA, AAPL, BRK-B."
        )

    # 3. Bloqueo de activos NO soportados (ETFs, cripto, futures, forex).
    #    La app analiza acciones individuales — los ETFs/cripto/futures no
    #    tienen earnings, P/E, sector específico, etc. Se cancela ANTES de
    #    gastar créditos de Anthropic en un análisis que sería irrelevante.
    if clean in _ETF_TICKERS:
        return False, "", (
            f"📊 **{clean}** es un ETF (fondo cotizado), no una acción individual. "
            f"DLP Analyzer solo analiza **acciones individuales** del NYSE/NASDAQ "
            f"(empresas con earnings, fundamentales, sector específico). "
            f"Prueba con tickers como **NVDA, AAPL, GOOGL, MSFT, AMD, TSLA**."
        )
    if clean in _CRYPTO_TICKERS:
        return False, "", (
            f"🪙 **{clean}** es una criptomoneda, no una acción del NYSE/NASDAQ. "
            f"DLP Analyzer solo analiza **acciones individuales** de empresas "
            f"cotizadas en NYSE/NASDAQ. Prueba con tickers como "
            f"**NVDA, AAPL, GOOGL, MSFT, AMD, TSLA**."
        )
    if clean in _FUTURES_FOREX:
        return False, "", (
            f"📈 **{clean}** parece ser un futuro o par de forex, no una acción "
            f"individual. DLP Analyzer solo analiza **acciones del NYSE/NASDAQ**. "
            f"Prueba con tickers como **NVDA, AAPL, GOOGL, MSFT, AMD, TSLA**."
        )

    # 4. Verificación de existencia con TradingView (gratis, ~200ms, sin
    #    rate-limit desde IPs cloud). Buscamos en AMBOS formatos posibles
    #    porque TradingView lista algunos tickers con punto (BRK.B) mientras
    #    yfinance/nuestro código usa guion (BRK-B).
    try:
        from tradingview_screener import Query, col

        def _search_tv(needle: str):
            try:
                _, df = (
                    Query()
                    .select("name", "exchange", "type")
                    .where(col("name") == needle)
                    .limit(3)
                    .get_scanner_data()
                )
                return df
            except Exception:
                return None

        # Primero intentar con el clean tal cual (BRK-B / NVDA / AAPL)
        df = _search_tv(clean)
        # Si no se encontró Y tiene guion, probar con punto (TradingView usa
        # ese formato para algunas clases B de mega-caps tipo BRK.B, BF.B)
        if (df is None or df.empty) and "-" in clean:
            df = _search_tv(clean.replace("-", "."))

        if df is None or df.empty:
            return False, "", (
                f"⚠️ El ticker **\"{clean}\"** no se encontró en NYSE/NASDAQ. "
                f"Verifica que esté bien escrito. Ejemplos: NVDA, AAPL, MSFT, "
                f"GOOGL, BRK-B."
            )

        # Confirmar que está en NYSE o NASDAQ (filtramos OTC/internacionales
        # porque la app no tiene datos confiables fuera de esos exchanges)
        for _, row in df.iterrows():
            exchange = str(row.get("exchange", "")).upper()
            if exchange in ("NYSE", "NASDAQ"):
                # Devolvemos el `clean` con guion para que sea compatible con
                # yfinance/persistencia (BRK-B, no BRK.B).
                return True, clean, ""

        # Existe pero no en NYSE/NASDAQ
        first_exchange = str(df.iloc[0].get("exchange", "")).upper()
        return False, "", (
            f"⚠️ El ticker **\"{clean}\"** existe pero cotiza en "
            f"**{first_exchange}**, no en NYSE/NASDAQ. Esta app solo soporta "
            f"acciones de mercados estadounidenses."
        )
    except Exception:
        # Network/TV falló — NO bloquear al usuario, dejar que el análisis
        # corra y falle ahí si el ticker realmente no existe. Esto evita
        # falsos negativos por problemas transitorios de red.
        return True, clean, ""


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
    """OHLCV diario o semanal para análisis técnico.

    Fuente primaria: yfinance. RESPALDO EN LA NUBE: si yfinance viene vacío
    (Yahoo bloquea/limita las IPs de datacenter en Render/Cloud → DataFrame
    vacío → de ahí venían los "nan" en target, Stage, 52W, RS, ATR en
    producción), se cae a Nasdaq, que SÍ responde OHLCV real en esas IPs (la
    misma API que ya usamos para insiders). Así el análisis técnico y de riesgo
    funciona igual en localhost y en producción."""
    key = f"price_{ticker}_{period}_{interval}"
    cached = _load_cache(key, ttl_hours=TTL_PRICE_DAILY)
    if cached:
        try:
            df = pd.DataFrame(cached)
            if not df.empty:
                # utc=True + tz_localize(None) tolera cachés VIEJOS con offsets
                # mixtos (-04:00/-05:00) y devuelve SIEMPRE un índice tz-naïve
                # uniforme (si no, el .intersection del RS con otro df tz-naïve
                # daba vacío → RS en blanco).
                idx = pd.to_datetime(df.index, utc=True, errors="coerce")
                df.index = idx.tz_localize(None)
                df = df[df.index.notna()]
                if not df.empty:
                    return df
        except Exception:
            pass

    df = pd.DataFrame()
    # Interruptor de PRUEBA: DLP_FORCE_TRADINGVIEW=1 simula producción (Yahoo y
    # Nasdaq bloqueados) → fuerza el respaldo de TradingView. Útil para verificar
    # en localhost que los datos llegan igual que en Render. Sin la variable, todo
    # funciona normal (yfinance → Nasdaq → TradingView).
    import os as _os
    if not _os.environ.get("DLP_FORCE_TRADINGVIEW"):
        try:
            df = _yt(ticker).history(period=period, interval=interval, auto_adjust=True)
        except Exception:
            df = pd.DataFrame()

        # Respaldo Nasdaq cuando yfinance no trae nada (típico en cloud).
        if df is None or df.empty:
            df = _get_price_history_from_nasdaq(ticker, period, interval)

    # Sin OHLCV (ni yfinance ni Nasdaq, o el toggle de prueba): devolvemos vacío
    # a propósito → get_technical_indicators / get_risk_levels / RS caen a
    # TradingView, que SÍ responde en cloud. La gráfica de velas se salta (no hay
    # histórico puntual en TV), pero todos los NÚMEROS quedan reales.
    if df is None or df.empty:
        return pd.DataFrame()

    # Índice tz-NAÏVE SIEMPRE: el índice de yfinance es tz-aware (America/New_York,
    # con offsets mixtos -04:00/-05:00 por el horario de verano). Guardado como
    # texto y releído, pd.to_datetime falla con esos offsets mixtos y ROMPE la
    # gráfica ("Tz-aware ... unless utc=True"). Lo volvemos naïve antes de cachear
    # y también en el objeto que devolvemos, para que sea uniforme y estable.
    try:
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)
    except (TypeError, AttributeError):
        pass

    # Cachear con índice en texto (json.dumps no serializa claves Timestamp) —
    # así el caché REALMENTE persiste y la próxima lectura es instantánea.
    try:
        df_cache = df.copy()
        df_cache.index = df_cache.index.astype(str)
        _save_cache(key, df_cache.to_dict())
    except Exception:
        pass
    return df


def _get_price_history_from_nasdaq(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """OHLCV histórico desde la API pública de Nasdaq (funciona en IPs de
    datacenter, a diferencia de yfinance). Devuelve un DataFrame con el MISMO
    formato que yfinance (columnas Open/High/Low/Close/Volume, índice de fechas
    ascendente). Vacío si falla. NUNCA lanza."""
    days = {"1mo": 40, "3mo": 100, "6mo": 190, "1y": 370, "2y": 740, "3y": 1100, "5y": 1850}.get(period, 740)
    frm = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    to = datetime.now().strftime("%Y-%m-%d")

    # La API de Nasdaq cubre NYSE **y** NASDAQ. Para acciones de CLASE (BRK-B,
    # BF-B) usa el PUNTO, no el guion que usa yfinance internamente → probamos
    # el ticker tal cual y también su variante con punto. assetclass: stocks y,
    # como respaldo, etf (para SPY, benchmark del RS).
    variants = [ticker.upper()]
    if "-" in ticker:
        variants.append(ticker.upper().replace("-", "."))

    def _fetch(tk: str, asset_class: str):
        return _nasdaq_json(
            f"/api/quote/{tk}/historical?assetclass={asset_class}"
            f"&fromdate={frm}&todate={to}&limit=9999"
        )

    try:
        rows = []
        for tk in variants:
            for ac in ("stocks", "etf"):
                data = _fetch(tk, ac)
                rows = (((data or {}).get("tradesTable") or {}).get("rows") or []) if data else []
                if rows:
                    break
            if rows:
                break
        recs = []
        for r in rows:
            try:
                d = pd.to_datetime(r.get("date"), format="%m/%d/%Y", errors="coerce")
                c = _nasdaq_num(r.get("close"))
                if d is None or pd.isna(d) or c is None:
                    continue
                recs.append({
                    "Date":   d,
                    "Open":   _nasdaq_num(r.get("open"))  or c,
                    "High":   _nasdaq_num(r.get("high"))  or c,
                    "Low":    _nasdaq_num(r.get("low"))   or c,
                    "Close":  c,
                    "Volume": _nasdaq_num(r.get("volume")) or 0.0,
                })
            except Exception:
                continue
        if not recs:
            return pd.DataFrame()
        df = pd.DataFrame(recs).set_index("Date").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        if interval == "1wk":
            df = df.resample("W").agg({"Open": "first", "High": "max", "Low": "min",
                                       "Close": "last", "Volume": "sum"}).dropna(subset=["Close"])
        return df
    except Exception:
        return pd.DataFrame()


def get_weekly_history(ticker: str, period: str = "3y") -> pd.DataFrame:
    return get_price_history(ticker, period=period, interval="1wk")


# ── Snapshot técnico vía TradingView (fuente INFALIBLE en cloud) ───────────
# TradingView (tradingview-screener) es la MISMA fuente del escáner, que ya
# funciona en Render "sin rate limit en cloud". Yahoo la puede bloquear pero
# TradingView NO. Da valores puntuales (no OHLCV histórico), suficientes para
# reconstruir TODOS los indicadores que la UI y el riesgo necesitan.
_TV_TECH_FIELDS = [
    "close", "SMA20", "SMA50", "SMA100", "SMA200", "RSI", "ATR",
    "price_52_week_high", "price_52_week_low",
    "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
    "MACD.macd", "MACD.signal", "Low.3M", "High.3M",
    # Target de analistas (el MISMO campo que usa get_company_info, probado en
    # Render): da un precio objetivo REAL sin depender de OHLCV.
    "price_target_average",
]


def _tv_row(ticker: str) -> dict:
    """Una fila de TradingView con campos técnicos para `ticker` (o {}).
    Prueba el ticker tal cual y su variante con punto (clases: BRK-B→BRK.B)."""
    variants = [ticker.upper()]
    if "-" in ticker:
        variants.append(ticker.upper().replace("-", "."))
    for tk in variants:
        try:
            from tradingview_screener import Query, col
            _, df = (Query().select(*_TV_TECH_FIELDS)
                     .where(col("name") == tk).limit(1).get_scanner_data())
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
        except Exception:
            continue
    return {}


def _sp500_benchmark_perf() -> dict:
    """Perf REAL del S&P 500 para el respaldo del Relative Strength en Render,
    calculado desde el histórico de SPY de Nasdaq (api.nasdaq.com responde en IPs
    de datacenter, igual que para insiders/holders). Se usa como benchmark cuando
    el OHLCV de yfinance viene vacío o corrupto en cloud.

    ¿Por qué no TradingView? El escáner de ACCIONES de TradingView no incluye
    ETFs ni índices (SPY/SPX/US500/VOO salen vacíos), y el promedio de mega-caps
    sobreestima el retorno (~38% vs ~17.5% real) → distorsionaría el RS. El SPY de
    Nasdaq da el número REAL (verificado: Perf.Y 17.5%, 6M 7.2%, 3M 3.5%, 1M 0.6%).

    Devuelve {"Perf.1M","Perf.3M","Perf.6M","Perf.Y"} en % (mismas claves que
    _tv_row, intercambiable como `benchmark`) o {} si falla. Cachea (mismo para
    todos los tickers). NUNCA lanza."""
    cached = _load_cache("sp500_benchmark_perf", ttl_hours=TTL_RS)
    if cached:
        return cached
    try:
        spy = _get_price_history_from_nasdaq("SPY", "1y", "1d")
        if spy is not None and not spy.empty and "Close" in spy.columns:
            c = pd.to_numeric(spy["Close"], errors="coerce").dropna()
            if len(c) > 30:
                out = {}
                for n, k in [(21, "Perf.1M"), (63, "Perf.3M"), (126, "Perf.6M"), (252, "Perf.Y")]:
                    if len(c) > n:
                        out[k] = float((c.iloc[-1] / c.iloc[-n] - 1) * 100)
                if "Perf.Y" not in out:  # <252 sesiones: usar el primer dato disponible
                    out["Perf.Y"] = float((c.iloc[-1] / c.iloc[0] - 1) * 100)
                if out.get("Perf.6M") is not None:
                    _save_cache("sp500_benchmark_perf", out)
                    return out
    except Exception:
        pass
    return {}


def _tradingview_technical_snapshot(ticker: str) -> dict:
    """Reconstruye el dict de indicadores (mismas claves que
    compute_technical_indicators) a partir de los valores puntuales de
    TradingView. {} si no hay datos. NUNCA lanza.
    Cacheado (TTL corto): técnico y riesgo lo piden en el mismo análisis y así
    no se golpea dos veces al escáner por ticker."""
    cached = _load_cache(f"tvsnap_{ticker}", ttl_hours=TTL_RS)
    if cached:
        return cached
    r = _tv_row(ticker)
    if not r:
        return {}
    try:
        def f(k):
            v = r.get(k)
            try:
                v = float(v)
                return v if v == v else None
            except (TypeError, ValueError):
                return None

        close = f("close")
        if not close:
            return {}
        ind = {"current_price": close}
        sma20, sma50, sma100, sma200 = f("SMA20"), f("SMA50"), f("SMA100"), f("SMA200")
        # TradingView no expone SMA150 → se aproxima con (SMA100+SMA200)/2
        sma150 = ((sma100 + sma200) / 2.0) if (sma100 and sma200) else None
        for n, ma in [(20, sma20), (50, sma50), (150, sma150), (200, sma200)]:
            ind[f"sma_{n}"] = ma
            ind[f"price_vs_sma{n}_pct"] = ((close / ma - 1) * 100) if ma else None
        ind["rsi_14"] = f("RSI")
        macd, sig = f("MACD.macd"), f("MACD.signal")
        if macd is not None:
            ind["macd"] = macd
            ind["macd_signal"] = sig
            ind["macd_hist"] = (macd - sig) if sig is not None else None
        atr = f("ATR")
        if atr is not None:
            ind["atr_14"] = atr
            ind["atr_pct"] = atr / close * 100
        hi52, lo52 = f("price_52_week_high"), f("price_52_week_low")
        ind["52w_high"] = hi52
        ind["52w_low"] = lo52
        ind["pct_from_52w_high"] = ((close / hi52 - 1) * 100) if hi52 else None
        ind["pct_from_52w_low"] = ((close / lo52 - 1) * 100) if lo52 else None
        ind["low_3m"] = f("Low.3M")
        ind["analyst_target"] = f("price_target_average")   # target real de analistas
        ind["stage"] = _compute_stage(pd.Series([close]), ind)
        for k, label in [("Perf.6M", "6m"), ("Perf.3M", "3m"), ("Perf.1M", "1m"), ("Perf.Y", "1y")]:
            v = f(k)
            if v is not None:
                ind[f"return_{label}"] = v
        ind["_source"] = "tradingview"
        try:
            _save_cache(f"tvsnap_{ticker}", ind)
        except Exception:
            pass
        return ind
    except Exception:
        return {}


def get_technical_indicators(ticker: str, df: pd.DataFrame = None) -> dict:
    """Indicadores técnicos con cadena de respaldo INFALIBLE:
    1) OHLCV (yfinance → Nasdaq) + compute_technical_indicators.
    2) Si viene vacío (Yahoo Y Nasdaq bloqueados en cloud) → snapshot de
       TradingView, que sí responde en Render. Así Stage, 52W, MA, RSI, ATR
       SIEMPRE tienen datos reales, en localhost y en producción."""
    if df is None:
        df = get_price_history(ticker, period="2y")
    if df is not None and not df.empty:
        ind = compute_technical_indicators(df)
        # Validar que los indicadores CLAVE sean números REALES. En cloud yfinance
        # a veces devuelve un df NO-vacío pero corrupto/incompleto → los cálculos
        # salen NaN. Si eso pasa, caemos a TradingView (que sí responde en Render)
        # en vez de propagar NaN. _isnum() trata NaN/inf como inválido.
        def _isnum(x):
            try:
                x = float(x); return x == x and x not in (float("inf"), float("-inf"))
            except (TypeError, ValueError):
                return False
        if ind and _isnum(ind.get("current_price")) and _isnum(ind.get("52w_high")) \
                and _isnum(ind.get("sma_50")) and _isnum(ind.get("rsi_14")):
            return ind
    return _tradingview_technical_snapshot(ticker)


def get_risk_levels(ticker: str, indicators: dict = None) -> dict:
    """Niveles de riesgo (entrada/stop/target/ATR/RR) SIEMPRE calculables, con
    la misma metodología que el agente de riesgo pero a prueba de bloqueos:
    usa indicadores reales (OHLCV o TradingView). {} si no hay ni precio."""
    ind = indicators or get_technical_indicators(ticker)
    if not ind:
        return {}
    try:
        price = ind.get("current_price")
        if not price:
            return {}
        atr = ind.get("atr_14") or (price * 0.03)
        hi52 = ind.get("52w_high") or (price * 1.25)
        # Stop: mínimo reciente (Low.3M) 2% abajo, o 2×ATR bajo el precio.
        low_ref = ind.get("low_3m")
        stop_swing = (low_ref * 0.98) if low_ref else None
        stop_atr = price - 2.0 * atr
        stop = max([s for s in (stop_swing, stop_atr) if s is not None] or [stop_atr])
        stop = min(stop, price * 0.99)   # nunca por encima del precio
        # Target: 1º el target REAL de analistas (TradingView, funciona en Render)
        # si implica subida; si no, el máximo de 52 semanas / +25%.
        analyst = ind.get("analyst_target")
        if analyst and analyst > price * 1.02:
            target = analyst
        else:
            target = hi52 if price < hi52 * 0.85 else price * 1.25
        risk = (price - stop) / price * 100
        reward = (target - price) / price * 100
        rr = (reward / risk) if risk > 0 else 0
        return {
            "current_price": round(price, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "atr_pct": round(atr / price * 100, 2),
            "risk_pct": round(risk, 1),
            "reward_pct": round(reward, 1),
            "rr": round(rr, 2),
        }
    except Exception:
        return {}


# ── Precio en vivo (siempre fresco — TTL 60 segundos) ────────────────────

def get_live_price(ticker: str) -> Optional[float]:
    """Obtiene el precio actual de un ticker, cacheado solo 60 segundos.
    Es ligero y rápido — usa fast_info que no descarga el JSON completo."""
    key = f"liveprice_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_LIVE_PRICE)
    if cached:
        return cached.get("price")

    try:
        stock = _yt(ticker)
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

    stock = _yt(ticker)
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
        # Short interest y beta con default None (no 0/1.0): un default "truthy"
        # o un 0 falso (a) impedía que el respaldo TradingView/Nasdaq rellenara
        # el hueco, y (b) mostraba "0% short" y "beta 1.00" INVENTADOS en cloud
        # en vez de "sin dato". None deja actuar a los respaldos y a la UI.
        "short_ratio":     info.get("shortRatio"),
        "short_percent":   info.get("shortPercentOfFloat"),
        "beta":            info.get("beta"),
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

    # Fallback TradingView: si yfinance.info falló (rate-limit en cloud),
    # los campos críticos vienen vacíos. Los completamos con TV que no
    # se rate-limita desde IPs cloud.
    needs_tv = (not result.get("market_cap") or
                not result.get("pe_ratio") or
                not result.get("forward_pe") or
                not result.get("ev_ebitda") or
                not result.get("revenue_ttm") or
                not result.get("profit_margin"))
    if needs_tv:
        tv = _get_company_info_from_tradingview(ticker)
        # Placeholders "truthy" que deben contar como VACÍO: sin esto, un sector
        # "Unknown" o un rating "N/A" bloqueaban el relleno de TradingView y se
        # quedaban para siempre en la UI.
        _PLACEHOLDERS = {"unknown", "n/a", "n/d", "", "none"}
        for k, v in tv.items():
            cur = result.get(k)
            is_empty = (not cur) or (isinstance(cur, str) and cur.strip().lower() in _PLACEHOLDERS)
            if is_empty and v is not None:
                result[k] = v
        # Re-derivar name si seguía con el ticker como nombre
        if result.get("name") == ticker and tv.get("name"):
            result["name"] = tv["name"]

    # Short interest: si yfinance no lo trajo (None en cloud), completar con
    # Nasdaq (acciones en corto / float; el float puede venir de TradingView).
    # Si tampoco hay, se queda None → la UI muestra "N/D", nunca un 0% falso.
    if result.get("short_percent") is None:
        si = _get_short_interest_from_nasdaq(
            ticker, float_shares=result.get("float_shares"))
        if si.get("short_percent") is not None:
            result["short_percent"] = si["short_percent"]
        if result.get("short_ratio") is None and si.get("short_ratio") is not None:
            result["short_ratio"] = si["short_ratio"]

    _save_cache(key, result)

    # Sobrescribir con precio en vivo si está disponible (más fresco)
    live = get_live_price(ticker)
    if live:
        result["current_price"] = live
    return result


def _get_company_info_from_tradingview(ticker: str) -> dict:
    """Fallback de fundamentales via TradingView para los campos críticos que
    se pierden cuando yfinance.info está rate-limitado (Render, Streamlit
    Cloud, AWS en general)."""
    try:
        from tradingview_screener import Query, col
        q = (
            Query()
            .select(
                "name", "description", "sector", "industry", "close",
                "market_cap_basic", "price_earnings_ttm",
                "price_earnings_forward", "enterprise_value_ebitda_ttm",
                "price_sales_ratio", "price_book_ratio",
                "dividend_yield_recent", "total_revenue_ttm",
                "gross_margin", "operating_margin", "net_margin",
                "return_on_equity", "return_on_assets",
                "debt_to_equity", "current_ratio_quarterly",
                "beta_1_year", "average_volume_30d_calc",
                "price_target_average", "recommendation_mark",
                "earnings_release_next_date",
                # Shares/float — necesarios para calcular short % del float en
                # cloud, y crecimiento/EPS forward para las barras y el Fwd P/E
                "float_shares_outstanding_current",
                "total_shares_outstanding_fundamental",
                "earnings_per_share_forecast_next_fy",
                "total_revenue_yoy_growth_ttm",
                "earnings_per_share_diluted_yoy_growth_ttm",
            )
            .where(col("name") == ticker.upper())
            .limit(1)
        )
        _, df = q.get_scanner_data()
        if df is None or df.empty:
            return {}

        row = df.iloc[0]

        def _f(key):
            v = row.get(key)
            if v is None:
                return None
            try:
                f = float(v)
                return f if f == f else None  # NaN check
            except (TypeError, ValueError):
                return None

        def _pct_to_dec(key):
            """TradingView devuelve margins como porcentaje (37.86 = 37.86%).
            yfinance los devuelve como decimal (0.3786). Convertimos para
            mantener compatibilidad con el resto del código que asume el
            formato yfinance (multiplica por 100 al renderizar)."""
            v = _f(key)
            return v / 100.0 if v is not None else None

        out = {
            "name":           str(row.get("description", "") or "") or None,
            "sector":         str(row.get("sector", "") or "") or None,
            "industry":       str(row.get("industry", "") or "") or None,
            "current_price":  _f("close"),
            "market_cap":     _f("market_cap_basic"),
            "pe_ratio":       _f("price_earnings_ttm"),
            "forward_pe":     _f("price_earnings_forward"),
            "ev_ebitda":      _f("enterprise_value_ebitda_ttm"),
            "ps_ratio":       _f("price_sales_ratio"),
            "pb_ratio":       _f("price_book_ratio"),
            # Margins: TV→decimal para compatibilidad con yfinance
            "dividend_yield": _pct_to_dec("dividend_yield_recent"),
            "revenue_ttm":    _f("total_revenue_ttm"),
            "profit_margin":  _pct_to_dec("net_margin"),
            "operating_margin_yf": _pct_to_dec("operating_margin"),
            "gross_margin_yf":     _pct_to_dec("gross_margin"),
            "roe_yf":              _pct_to_dec("return_on_equity"),
            "roa_yf":              _pct_to_dec("return_on_assets"),
            # Crecimiento YoY: TV lo da en % → a decimal (formato yfinance) para
            # que compute_quality_ratios lo multiplique por 100 correctamente.
            # Sin esto, la barra "Crecimiento" salía plana en cloud.
            "revenue_growth_yf":   _pct_to_dec("total_revenue_yoy_growth_ttm"),
            "earnings_growth_yf":  _pct_to_dec("earnings_per_share_diluted_yoy_growth_ttm"),
            # Ratios sin conversión (mismo formato en YF y TV)
            "debt_equity_yf":      _f("debt_to_equity"),
            "current_ratio_yf":    _f("current_ratio_quarterly"),
            "beta":           _f("beta_1_year"),
            "avg_volume":     _f("average_volume_30d_calc"),
            "target_price":   _f("price_target_average"),
            # Shares/float — para el cálculo de short % del float en cloud
            "float_shares":       _f("float_shares_outstanding_current"),
            "shares_outstanding": _f("total_shares_outstanding_fundamental"),
        }
        # Forward P/E calculado si TV no lo trae directo (precio / EPS forward
        # de consenso). Garantiza que el Forward P/E aparezca en cloud.
        if out.get("forward_pe") is None:
            close_px = _f("close")
            fwd_eps = _f("earnings_per_share_forecast_next_fy")
            if close_px and fwd_eps and fwd_eps > 0:
                out["forward_pe"] = round(close_px / fwd_eps, 2)

        # recommendation_mark de TV: 1=Strong Buy … 5=Strong Sell → etiqueta
        rec_mark = _f("recommendation_mark")
        if rec_mark is not None:
            out["analyst_rating"] = (
                "strong_buy" if rec_mark <= 1.5 else
                "buy"        if rec_mark <= 2.5 else
                "hold"       if rec_mark <= 3.5 else
                "sell"       if rec_mark <= 4.5 else
                "strong_sell"
            )
        # Limpiar None entries
        return {k: v for k, v in out.items() if v is not None}
    except Exception:
        return {}


# ── Métricas financieras ───────────────────────────────────────────────────

def get_financials(ticker: str) -> dict:
    key = f"financials_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_FINANCIALS)
    if cached:
        return cached

    stock = _yt(ticker)
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

    # Debt/Equity SIEMPRE como RATIO (0.57 = deuda es 57% del patrimonio).
    # yfinance devuelve `debtToEquity` en forma PORCENTUAL (57.6 = 0.576 de
    # ratio), por eso antes se veía "57.6" en vez de "0.58" y el color (umbrales
    # 0.5/1.5, que son de RATIO) siempre salía rojo. Lo dividimos entre 100 para
    # dejarlo como ratio, igual que la rama calculada desde el balance.
    de_yf = info.get("debt_equity_yf")
    if de_yf is not None:
        try:
            _de = float(de_yf)
            # Heurística: si viene >5 es porcentaje (57.6) → a ratio; si ya es
            # pequeño (1.38) es ratio y se deja igual.
            ratios["debt_to_equity"] = (_de / 100.0) if _de > 5 else _de
        except (TypeError, ValueError):
            pass
    if "debt_to_equity" not in ratios and debt and equity and equity > 0:
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
        ma_last = float(ma.iloc[-1]) if not ma.empty else None
        # pd.isna() atrapa NaN (media sin suficientes datos) → evita nan% aguas abajo
        if ma_last is not None and pd.isna(ma_last):
            ma_last = None
        indicators[f"sma_{n}"] = ma_last
        indicators[f"price_vs_sma{n}_pct"] = (
            float((close.iloc[-1] / ma_last - 1) * 100) if ma_last else None)

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
    # 52 semanas — nan-safe: si el máximo/mínimo sale NaN (datos con huecos),
    # se deja None en vez de propagar nan a los "%" que se muestran en la UI.
    _hi52 = float(high.tail(252).max())
    _lo52 = float(low.tail(252).min())
    _px = float(close.iloc[-1])
    _hi52 = None if pd.isna(_hi52) else _hi52
    _lo52 = None if pd.isna(_lo52) else _lo52
    indicators["52w_high"] = _hi52
    indicators["52w_low"] = _lo52
    indicators["pct_from_52w_high"] = float((_px / _hi52 - 1) * 100) if _hi52 else None
    indicators["pct_from_52w_low"] = float((_px / _lo52 - 1) * 100) if _lo52 else None

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

    def _perf(row, k):
        try:
            v = float(row.get(k))
            return v if v == v else None
        except (TypeError, ValueError):
            return None

    # Respaldo INFALIBLE (Render): RS con Perf puntuales. La acción se toma de
    # TradingView (responde en datacenter); el benchmark S&P500 se toma del SPY
    # histórico de Nasdaq (número REAL, también responde en datacenter). El ETF
    # SPY no está en el escáner de acciones de TradingView, por eso NO se usa
    # _tv_row para el benchmark. Muta `result`; devuelve True si logró rs_6m real.
    def _rs_via_tradingview() -> bool:
        try:
            st = _tv_row(ticker)
            if benchmark.upper() in ("SPY", "^GSPC", "GSPC", "SPX", "US500", "VOO", "IVV"):
                bm = _sp500_benchmark_perf()
            else:
                bm = _tv_row(benchmark)
            if not (st and bm):
                return False
            for tvk, rsk in [("Perf.1M", "rs_1m"), ("Perf.3M", "rs_3m"), ("Perf.6M", "rs_6m")]:
                a, b = _perf(st, tvk), _perf(bm, tvk)
                if a is not None and b is not None:
                    result[rsk] = float(a - b)
            a12, b12 = _perf(st, "Perf.Y"), _perf(bm, "Perf.Y")
            if a12 is not None and b12 is not None:
                result["rs_composite"] = float(a12 - b12)
            return result.get("rs_6m") is not None
        except Exception:
            return False

    # Datos utilizables = no-vacíos y con ≥20 cierres reales. Detecta el caso de
    # Render donde Yahoo devuelve un DataFrame no-vacío pero LLENO DE NaN.
    def _usable(df) -> bool:
        try:
            return (not df.empty) and "Close" in df.columns \
                and pd.to_numeric(df["Close"], errors="coerce").notna().sum() >= 20
        except Exception:
            return False

    if not _usable(stock_data) or not _usable(spy_data) \
            or len(stock_data.index.intersection(spy_data.index)) < 20:
        if _rs_via_tradingview():
            _save_cache(key, result)
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

    # Red de seguridad: si la data OHLCV salió parcialmente corrupta y el RS
    # quedó NaN, reconstruir con TradingView antes de devolver/cachear.
    rs6m = result.get("rs_6m")
    if rs6m is None or rs6m != rs6m:
        result = {"rs_score": 50, "rs_6m": None, "rs_3m": None, "rs_1m": None}
        if not _rs_via_tradingview():
            return result

    _save_cache(key, result)
    return result


# ── Holders e institucionales ──────────────────────────────────────────────

def _nasdaq_num(s):
    """Convierte '1,234.5', '$1,234', '8.94%' → float. None si no se puede."""
    if s is None:
        return None
    try:
        cleaned = re.sub(r"[,$%\s]", "", str(s))
        if cleaned in ("", "-", "N/A"):
            return None
        v = float(cleaned)
        return v if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def _nasdaq_json(path: str) -> Optional[dict]:
    """GET a la API pública de Nasdaq (api.nasdaq.com). Nasdaq cubre TODAS las
    acciones de NASDAQ y NYSE y no rate-limita las IPs de datacenter como sí
    hace Yahoo. Devuelve el dict 'data' de la respuesta, o None. NUNCA lanza."""
    url = f"https://api.nasdaq.com{path}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        return payload.get("data") if isinstance(payload, dict) else None
    except Exception:
        return None


def _get_insiders_from_nasdaq(ticker: str) -> dict:
    """Fallback de transacciones de insiders via Nasdaq cuando yfinance falla
    (rate-limit en cloud). Devuelve {insider_transactions, recent_insider_buys,
    recent_insider_sells} en el MISMO formato que get_holders_data. NUNCA lanza."""
    result: dict = {}
    try:
        data = _nasdaq_json(
            f"/api/company/{ticker.upper()}/insider-trades"
            "?limit=20&type=ALL&sortColumn=lastDate&sortOrder=DESC"
        )
        if not data:
            return result
        rows = (((data.get("transactionTable") or {}).get("table") or {})
                .get("rows") or [])
        txns, buys, sells = [], 0, 0
        for row in rows[:20]:
            ttype = str(row.get("transactionType", "")).lower()
            if "buy" in ttype or "purchase" in ttype:
                tipo, is_buy = "compra", True
            elif "sell" in ttype or "sale" in ttype:
                tipo, is_buy = "venta", False
            elif "option" in ttype or "grant" in ttype or "award" in ttype:
                tipo, is_buy = "concesión", None
            else:
                tipo, is_buy = "otra", None
            if is_buy is True:
                buys += 1
            elif is_buy is False:
                sells += 1
            shares = _nasdaq_num(row.get("sharesTraded")) or 0.0
            price = _nasdaq_num(row.get("lastPrice")) or 0.0
            txns.append({
                "date": str(row.get("lastDate", ""))[:10],
                "insider": str(row.get("insider", "")).title(),
                "position": str(row.get("relation", "")),
                "shares": shares,
                "value": shares * price,
                "type": tipo,
                "text": str(row.get("transactionType", "")),
            })
        if txns:
            result["insider_transactions"] = txns
            result["recent_insider_buys"] = buys
            result["recent_insider_sells"] = sells
    except Exception:
        pass
    return result


def _get_short_interest_from_nasdaq(ticker: str, float_shares=None) -> dict:
    """Fallback de short interest via Nasdaq cuando yfinance falla (bloqueado
    en cloud). El endpoint da 'interest' (acciones en corto) y 'daysToCover'.
    Calcula short_percent = interest / float_shares si hay float (el float
    puede venir de TradingView). Devuelve {short_percent, short_ratio} — solo
    lo que consigue — o {}. NUNCA lanza.

    LÍMITE conocido: este endpoint solo publica el short interest de acciones
    listadas en NASDAQ (verificado: AAPL sí, MCD/NYSE devuelve 0 filas). Para
    NYSE el valor queda None y la UI muestra "N/D" — honesto, nunca un 0% falso."""
    rows = []
    variants = [ticker.upper()]
    if "-" in ticker:
        variants.append(ticker.upper().replace("-", "."))
    try:
        for tk in variants:
            data = _nasdaq_json(
                f"/api/quote/{tk}/short-interest?assetClass=stocks"
            )
            rows = (((data or {}).get("shortInterestTable") or {}).get("rows")) or []
            if rows:
                break
        if not rows:
            return {}
        latest = rows[0]  # el más reciente (settlementDate desc)
        out = {}
        dtc = _nasdaq_num(latest.get("daysToCover"))
        if dtc is not None:
            out["short_ratio"] = dtc
        interest = _nasdaq_num(latest.get("interest"))
        fs = _nasdaq_num(float_shares) if float_shares else None
        if interest is not None and fs and fs > 0:
            # yfinance devuelve short_percent como fracción (0.0137 = 1.37%)
            out["short_percent"] = interest / fs
        return out
    except Exception:
        return {}


def _get_institutional_from_nasdaq(ticker: str) -> dict:
    """Fallback de holders INSTITUCIONALES vía Nasdaq cuando yfinance falla
    (bloqueado en IPs de datacenter — así se guardaron análisis sin la gráfica
    de Propiedad Institucional en producción). Devuelve
    {top_institutions: [{"Holder", "% Out"}], institutional_ownership_pct} en el
    MISMO formato que consume build_holders_bars. NUNCA lanza.

    OJO: el endpoint se llama SIN query string — con parámetros (?limit=…)
    api.nasdaq.com responde 200 pero con cuerpo no-JSON. Probado en vivo.
    Tickers de clase: Nasdaq usa punto (BRK.B), no el guion de yfinance."""
    variants = [ticker.upper()]
    if "-" in ticker:
        variants.append(ticker.upper().replace("-", "."))
    for tk in variants:
        try:
            data = _nasdaq_json(f"/api/company/{tk}/institutional-holdings")
            if not data:
                continue
            rows = (((data.get("holdingsTransactions") or {}).get("table") or {})
                    .get("rows") or [])
            own = data.get("ownershipSummary") or {}
            # Acciones en circulación (en millones) para calcular el % de cada fondo
            shares_out_m = _nasdaq_num(
                (own.get("ShareoutstandingTotal") or {}).get("value"))
            inst_pct = _nasdaq_num(
                (own.get("SharesOutstandingPCT") or {}).get("value"))
            # SharesOutstandingPCT llega como "85.92%" (→ 85.92) pero en algunos
            # tickers viene como fracción "0.86" → normalizar a 0-100.
            if inst_pct is not None and inst_pct <= 1:
                inst_pct *= 100
            top = []
            for row in rows[:10]:
                name = str(row.get("ownerName", "")).strip()
                shares = _nasdaq_num(row.get("sharesHeld"))
                if not name or shares is None:
                    continue
                pct = (shares / (shares_out_m * 1e6) * 100) \
                    if shares_out_m and shares_out_m > 0 else None
                # "% Out" en PORCENTAJE (10.2 = 10.2%): build_holders_bars deja
                # pasar tal cual los valores >= 1.
                top.append({"Holder": name,
                            "% Out": round(pct, 2) if pct is not None else 0.0})
            if top:
                out = {"top_institutions": top}
                if inst_pct is not None:
                    out["institutional_ownership_pct"] = float(inst_pct)
                return out
        except Exception:
            continue
    return {}


def get_holders_data(ticker: str) -> dict:
    key = f"holders_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_HOLDERS)
    if cached:
        # Auto-curación: un caché guardado ANTES del respaldo institucional (o
        # durante un bloqueo de yfinance) puede venir sin top_institutions.
        # Se completa desde Nasdaq y se re-guarda, en vez de servir el hueco
        # durante todo el TTL.
        if not cached.get("top_institutions"):
            ni = _get_institutional_from_nasdaq(ticker)
            if ni.get("top_institutions"):
                cached["top_institutions"] = ni["top_institutions"]
                if cached.get("institutional_ownership_pct") is None \
                        and ni.get("institutional_ownership_pct") is not None:
                    cached["institutional_ownership_pct"] = ni["institutional_ownership_pct"]
                _save_cache(key, cached)
        return cached

    stock = _yt(ticker)
    result = {}

    try:
        inst = stock.institutional_holders
        if inst is not None and not inst.empty:
            result["top_institutions"] = inst.head(10).to_dict(orient="records")
            # yfinance cambió la columna de "% Out" a "pctHeld"; soportamos
            # ambas. El ×100 unifica la escala con la del respaldo Nasdaq
            # (85.92 = 85.92%): antes este camino devolvía FRACCIÓN y el otro
            # porcentaje → escalas mezcladas aguas abajo.
            pct_col = "pctHeld" if "pctHeld" in inst.columns else ("% Out" if "% Out" in inst.columns else None)
            if pct_col:
                result["institutional_ownership_pct"] = float(inst[pct_col].sum()) * 100
    except Exception:
        pass

    # ── Transacciones de insiders (compras/ventas de directivos) ────────────
    # yfinance renombró columnas: la descripción vive en "Text" ("Sale at
    # price…", "Purchase at price…", "Stock Award(Grant)…") y la fecha en
    # "Start Date". Clasificamos el tipo desde "Text" y contamos compras/ventas.
    try:
        insiders = stock.insider_transactions
        if insiders is not None and not insiders.empty:
            recent = insiders.head(20).copy()
            text_col = next((c for c in ("Text", "Transaction") if c in recent.columns), None)
            txt = (recent[text_col].astype(str).str.lower()
                   if text_col else pd.Series([""] * len(recent), index=recent.index))
            is_buy = txt.str.contains("purchase|buy", na=False) & ~txt.str.contains("sale|sell", na=False)
            is_sell = txt.str.contains("sale|sell", na=False)
            result["recent_insider_buys"] = int(is_buy.sum())
            result["recent_insider_sells"] = int(is_sell.sum())

            date_col = next((c for c in ("Start Date", "Date") if c in recent.columns), None)
            txns = []
            for _, row in recent.iterrows():
                t = str(row.get(text_col, "")) if text_col else ""
                tl = t.lower()
                if ("purchase" in tl or "buy" in tl) and "sale" not in tl:
                    tipo = "compra"
                elif "sale" in tl or "sell" in tl:
                    tipo = "venta"
                elif "gift" in tl:
                    tipo = "donación"
                elif "award" in tl or "grant" in tl:
                    tipo = "concesión"
                else:
                    tipo = "otra"
                try:
                    shares = float(row.get("Shares", 0) or 0)
                except Exception:
                    shares = 0.0
                try:
                    value = float(row.get("Value", 0) or 0)
                except Exception:
                    value = 0.0
                txns.append({
                    "date": str(row.get(date_col, ""))[:10] if date_col else "",
                    "insider": str(row.get("Insider", "")),
                    "position": str(row.get("Position", "")),
                    "shares": shares,
                    "value": value,
                    "type": tipo,
                    "text": t,
                })
            result["insider_transactions"] = txns
    except Exception:
        pass

    # Fallback Nasdaq para los holders INSTITUCIONALES si yfinance no los trajo
    # (bloqueado en cloud → la gráfica de Propiedad Institucional salía vacía).
    # Disparadores POR CAMPO: también dispara si solo falta el % total.
    # Rellena solo lo que falta; nunca pisa datos buenos de yfinance.
    need_owners = not result.get("top_institutions")
    need_pct = result.get("institutional_ownership_pct") is None
    if need_owners or need_pct:
        ni = _get_institutional_from_nasdaq(ticker)
        if need_owners and ni.get("top_institutions"):
            result["top_institutions"] = ni["top_institutions"]
        if need_pct and ni.get("institutional_ownership_pct") is not None:
            result["institutional_ownership_pct"] = ni["institutional_ownership_pct"]

    # Fallback Nasdaq SOLO para insiders si yfinance no los trajo (rate-limit en
    # cloud). No toca la ruta institucional. Rellena solo lo que falta.
    if not result.get("insider_transactions"):
        nd = _get_insiders_from_nasdaq(ticker)
        if nd.get("insider_transactions"):
            result["insider_transactions"] = nd["insider_transactions"]
            result["recent_insider_buys"] = nd.get("recent_insider_buys", 0)
            result["recent_insider_sells"] = nd.get("recent_insider_sells", 0)

    try:
        # major_holders es la fuente MÁS confiable del % total institucional
        # (institutionsPercentHeld) e insiders (insidersPercentHeld).
        mh = stock.major_holders
        if mh is not None and not mh.empty:
            result["major_holders_raw"] = mh.to_dict()
            try:
                col = mh.columns[0]

                def _mh(name):
                    if name in mh.index:
                        v = mh.loc[name, col]
                        return float(v) if v is not None else None
                    return None

                inst_held = _mh("institutionsPercentHeld")
                if inst_held is not None:
                    result["institutional_ownership_pct"] = inst_held * 100
                ins_held = _mh("insidersPercentHeld")
                if ins_held is not None:
                    result["insiders_percent_held"] = ins_held * 100
            except Exception:
                pass
    except Exception:
        pass

    # NO cachear un resultado inútil: un fallo transitorio de red no debe
    # quedar congelado como "sin holders" durante todo el TTL (la auto-curación
    # de arriba mitiga, pero mejor no guardar el hueco de entrada).
    if result.get("top_institutions") or result.get("institutional_ownership_pct") is not None \
            or result.get("insider_transactions"):
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

    stock = _yt(ticker)
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
            df = _yt(sym).history(period="3mo")
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
            df = _yt(etf).history(period="1y")
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

def get_earnings_from_tradingview(ticker: str) -> dict:
    """Fallback de earnings via TradingView cuando yfinance falla.
    NO reemplaza a get_earnings_data — solo complementa cuando ese
    devuelve vacío (rate-limit de Yahoo en cloud)."""
    try:
        from tradingview_screener import Query, col
        from datetime import datetime
        q = (
            Query()
            .select("name", "earnings_release_next_date",
                    "earnings_release_date", "earnings_per_share_basic_ttm")
            .where(col("name") == ticker.upper())
            .limit(1)
        )
        _, df = q.get_scanner_data()
        if df is None or df.empty:
            return {}

        row = df.iloc[0]
        result = {}
        # TradingView devuelve epoch timestamp (segundos)
        ts_next = row.get("earnings_release_next_date")
        try:
            ts_next_val = float(ts_next) if ts_next is not None else 0
        except (TypeError, ValueError):
            ts_next_val = 0
        if ts_next_val > 0:
            dt_next = datetime.fromtimestamp(int(ts_next_val))
            days_to_next = (dt_next - datetime.now()).days
            result["next_earnings"] = dt_next.strftime("%Y-%m-%d")
            result["days_to_next_earnings"] = days_to_next
            result["next_earnings_proximity"] = (
                "🔥 INMINENTE" if days_to_next <= 7 else
                "⚡ PRÓXIMO"  if days_to_next <= 30 else
                "📅 LEJANO"
            )
        return result
    except Exception:
        return {}


def _get_earnings_from_nasdaq(ticker: str) -> dict:
    """Fallback del HISTORIAL de earnings (surprises + beat rate) via Nasdaq
    cuando yfinance falla. TradingView solo da la fecha del próximo reporte, no
    el track record; Nasdaq expone los últimos ~4 trimestres de EPS estimado vs
    reportado para CUALQUIER acción de NASDAQ/NYSE. NUNCA lanza excepción.
    Devuelve {earnings_history, avg_surprise, beat_count} o {}."""
    try:
        rows = []
        variants = [ticker.upper()]
        if "-" in ticker:
            variants.append(ticker.upper().replace("-", "."))
        for tk in variants:
            data = _nasdaq_json(f"/api/company/{tk}/earnings-surprise")
            rows = (((data or {}).get("earningsSurpriseTable") or {}).get("rows")) or []
            if rows:
                break
        now = pd.Timestamp.now()
        surprises = []
        for row in rows:
            est = _nasdaq_num(row.get("consensusForecast"))
            act = _nasdaq_num(row.get("eps"))
            surp = _nasdaq_num(row.get("percentageSurprise"))
            if surp is None and est not in (None, 0) and act is not None:
                surp = (act - est) / abs(est) * 100
            if surp is None:
                continue
            raw_date = str(row.get("dateReported", ""))
            try:
                iso = datetime.strptime(raw_date, "%m/%d/%Y")
                date_str = iso.strftime("%Y-%m-%d")
                days_ago = (now - pd.Timestamp(iso)).days
            except (ValueError, TypeError):
                date_str = raw_date[:10]
                days_ago = None
            surprises.append({
                "date": date_str,
                "days_ago": days_ago,
                "estimate": est,
                "actual": act,
                "surprise_pct": float(surp),
            })
        if not surprises:
            return {}
        return {
            "earnings_history": surprises,
            "avg_surprise": sum(s["surprise_pct"] for s in surprises) / len(surprises),
            "beat_count": sum(1 for s in surprises if s["surprise_pct"] > 0),
        }
    except Exception:
        return {}


def get_earnings_data(ticker: str) -> dict:
    """Earnings con días desde HOY al próximo reporte calculados explícitamente.
    Si yfinance falla (rate-limit en cloud), cae automáticamente a TradingView
    (fecha del próximo reporte) y a Nasdaq (historial de surprises + beat rate)
    para garantizar que estas secciones nunca queden vacías."""
    key = f"earnings_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_EARNINGS)
    if cached:
        return cached

    stock = _yt(ticker)
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

    # Si yfinance no consiguió el next_earnings (rate-limit en cloud típico),
    # caemos a TradingView que NO tiene rate-limits desde AWS.
    if not result.get("next_earnings"):
        tv_fallback = get_earnings_from_tradingview(ticker)
        if tv_fallback.get("next_earnings"):
            result.update(tv_fallback)

    # HISTORIAL de surprises: TradingView solo da la fecha del próximo reporte,
    # no el track record. Si yfinance no lo trajo (bloqueado en cloud), Nasdaq
    # expone los últimos ~4 trimestres de EPS estimado vs reportado → la
    # gráfica de sorpresas y la tasa de aciertos nunca quedan vacías.
    if not result.get("earnings_history"):
        nd = _get_earnings_from_nasdaq(ticker)
        if nd.get("earnings_history"):
            result["earnings_history"] = nd["earnings_history"]
            result.setdefault("avg_surprise", nd.get("avg_surprise"))
            result.setdefault("beat_count", nd.get("beat_count"))

    # NO cachear un resultado inútil: un fallo transitorio no debe congelar
    # "sin earnings" durante todo el TTL.
    if result.get("next_earnings") or result.get("earnings_history"):
        _save_cache(key, result)
    return result

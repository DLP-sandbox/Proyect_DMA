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

# ── Divisa de reporte (ADRs y empresas extranjeras) ────────────────────────
# POR QUÉ EXISTE. yfinance mete DOS divisas en el MISMO diccionario. Para un
# ADR como CIB (Bancolombia) `currency` es USD —precio, market cap y dividendo
# del ADR van en dólares— pero `financialCurrency` es COP: ingresos, EBITDA,
# FCF, deuda y book value vienen en PESOS. Todo ratio que mezcle las dos
# escalas sale multiplicado por ~4000. Medido en producción:
#   · pb_ratio  = precio USD / bookValue COP → 0.00204   (el real es 2.06)
#   · fcf_yield = FCF COP / market cap USD   → 46470 %   (¡y se pintaba VERDE!)
#   · al prompt del agente le llegaba «2025: $27494.93B» de ingresos de un
#     banco que factura 10,5 mil millones de dólares.
# EL ARREGLO NO CONVIERTE DIVISAS (no queremos tipos de cambio en la app):
# prefiere las fuentes que YA publican en USD (agregados de TradingView y el
# /financials de Nasdaq) y, cuando no hay ninguna, NEUTRALIZA el valor a None
# para que la UI pinte «—» en vez de un número falso.

def _divisa_de_reporte_ajena(info_yf: dict) -> bool:
    """True si la empresa REPORTA sus cuentas en una divisa distinta de aquella
    en la que COTIZA. Deliberadamente conservador: si el dato falta devuelve
    False, así las acciones USA —y cualquier caso dudoso— siguen EXACTAMENTE
    el camino de siempre. Medido: AAPL/KO/MSFT USD/USD → False; CIB USD/COP,
    ITUB y PBR USD/BRL → True. NUNCA lanza."""
    try:
        cotiza  = str(info_yf.get("currency") or "USD").upper().strip()
        reporta = str(info_yf.get("financialCurrency") or "").upper().strip()
        return bool(reporta) and reporta != cotiza
    except Exception:
        return False


# Bandas de plausibilidad de los múltiplos que se corrompen al mezclar divisas.
# Criterio DELIBERADAMENTE ESTRECHO, con tres condiciones simultáneas:
#   (1) lista blanca de claves — nada fuera de aquí se toca jamás;
#   (2) el valor ACTUAL tiene que estar FUERA de la banda (o sea, roto);
#   (3) el valor de TradingView tiene que estar DENTRO.
# Si los dos son razonables NO SE TOCA NADA: ante la duda gana el dato que ya
# estaba. La razón exacta de este criterio: para CIB el P/E de TradingView
# (46.35) discrepa del de yfinance (10.49) porque TV mezcla la acción local con
# el ADR (ratio 4:1) — los dos caen dentro de la banda, así que el P/E NO se
# pisa. En cambio pb_ratio=0.00204 cae fuera y TV trae 2.063 dentro → ese SÍ.
_BANDAS_MULTIPLO = {
    "pb_ratio":      (0.05, 100.0),
    "ps_ratio":      (0.05, 100.0),
    "ev_ebitda":     (0.5,  200.0),
    "ev_revenue_yf": (0.05, 100.0),
    "pe_ratio":      (0.5,  500.0),
    "forward_pe":    (0.5,  500.0),
}


def _en_banda(clave, valor) -> bool:
    """True si el valor es un número dentro de la banda plausible de esa clave."""
    try:
        lo, hi = _BANDAS_MULTIPLO[clave]
        v = float(valor)
        return v == v and lo <= v <= hi
    except (TypeError, ValueError, KeyError):
        return False


# Agregados ABSOLUTOS que yfinance publica en la divisa de REPORTE. Con divisa
# mixta hay que sustituirlos por los de TradingView, que los publica en dólares
# (su columna `currency` devuelve USD también para los ADR). No basta con
# «rellenar si está vacío»: aquí el valor de yfinance EXISTE, solo que está en
# pesos/reales/dólares taiwaneses, y mezclado con el market cap en USD produce
# ratios absurdos. Medido: TSM revenue 4.440.492 M TWD → 142.820 M USD.
_AGREGADOS_DIVISA = ("revenue_ttm", "ebitda_yf", "fcf_yf", "ocf_yf",
                     "total_cash_yf", "total_debt_yf", "enterprise_value_yf",
                     "book_value_yf")

# Múltiplos que DIVIDEN una magnitud en divisa de cotización (precio, market
# cap, EV) entre otra en divisa de reporte → estructuralmente rotos con divisa
# mixta. Se prefiere TradingView y, si no es plausible, se neutralizan.
#
# OJO: `pe_ratio` y `forward_pe` NO entran aquí a propósito. Medido: el P/E de
# yfinance es COHERENTE en dólares incluso para los ADR, porque su `trailingEps`
# ya viene por acción del ADR y en USD (CIB 90.14/8.66 = 10.41 ✓, TSM
# 414.00/11.39 = 36.35 ✓, PBR 18.36/3.20 = 5.74 ✓). Es justo el caso donde
# TradingView se equivoca: para CIB da 45.85 porque mezcla la acción local con
# el ADR (ratio 4:1). Pisarlo con TV empeoraría el dato.
_MULTIPLOS_DIVISA = ("pb_ratio", "ps_ratio", "ev_revenue_yf", "ev_ebitda")


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
        # OJO: `.get("longName", ticker)` NO protege aquí, porque yfinance
        # devuelve la clave PRESENTE con valor None para bastantes acciones
        # (KO es un caso real: longName=None, shortName='Coca-Cola Company
        # (The)'). El resultado era una cabecera que decía "KO | KO" en vez del
        # nombre de la empresa. Y el respaldo de TradingView no lo salvaba,
        # porque solo se consulta cuando faltan datos FINANCIEROS, no el nombre.
        # `or` encadenado: longName → shortName → el ticker como último recurso.
        "name":            info.get("longName") or info.get("shortName") or ticker,
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
        # yfinance devuelve dividendYield en PUNTOS PORCENTUALES (KO=2.45,
        # AAPL=0.35), pero todo el código que lo consume asume el formato
        # decimal y lo multiplica ×100 al renderizar → la Quick View pintaba
        # «245.00%» para KO y «35.00%» para AAPL, y ese mismo número llegaba
        # al prompt del agente. Se convierte AQUÍ, en el origen, para que la
        # clave signifique siempre lo mismo (decimal, como el resto de
        # márgenes). La rama de TradingView ya guarda decimal (_pct_to_dec),
        # así que las dos fuentes quedan en la misma unidad.
        "dividend_yield":  (info.get("dividendYield") or 0) / 100.0,
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
        # ── Dividendo por acción, en dólares (INFORMATIVO) ────────────────────
        # Se leen aquí porque el objeto `info` YA está descargado: sacarlas
        # cuesta CERO llamadas de red. Son claves NUEVAS que ningún prompt de
        # agente imprime, así que la IA ve exactamente lo mismo que antes.
        # Las consume get_dividend_info(); OJO: trailingAnnualDividendRate
        # viene contaminado en los ADR (CIB da 0.0 teniendo dividendo, ITUB lo
        # da en reales), por eso nunca se usa como fuente primaria.
        "dividend_rate_yf":       info.get("dividendRate"),                 # anualizado vigente
        "last_dividend_value_yf": info.get("lastDividendValue"),            # importe del último pago
        "trailing_div_rate_yf":   info.get("trailingAnnualDividendRate"),   # 12m atrás
        # Divisa en la que la empresa REPORTA sus cuentas (≠ la de cotización en
        # los ADR). La consume get_financials para saber si debe rehacer los
        # estados financieros desde una fuente en dólares.
        "financial_currency": (str(info.get("financialCurrency") or "").upper() or None),
    }

    # Guarda maestra de todo el arreglo de divisa mixta. Para AAPL/KO/MSFT —y
    # para el caso de yfinance bloqueado, donde `info` viene vacío— es False y
    # NI UNA sola línea del arreglo llega a ejecutarse.
    _mixta = _divisa_de_reporte_ajena(info)

    # Fallback TradingView: si yfinance.info falló (rate-limit en cloud),
    # los campos críticos vienen vacíos. Los completamos con TV que no
    # se rate-limita desde IPs cloud.
    needs_tv = (not result.get("market_cap") or
                not result.get("pe_ratio") or
                not result.get("forward_pe") or
                not result.get("ev_ebitda") or
                not result.get("revenue_ttm") or
                not result.get("profit_margin"))
    # Con divisa MIXTA hay que llamar a TradingView SIEMPRE, aunque yfinance
    # tenga todos los campos de la compuerta: el problema no es que falten, es
    # que están en la divisa equivocada. Medido: TSM y PBR daban needs_tv=False
    # (yfinance trae los 6) y por eso el arreglo no llegaba a ejecutarse nunca.
    if needs_tv or _mixta:
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

        # Reparación de valores CORRUPTOS (no vacíos, que ya los cubre el bucle
        # de arriba). Solo se activa cuando la empresa reporta en OTRA divisa,
        # que es la única causa conocida de estos números. Para cualquier acción
        # USA `_mixta` es False y este bloque entero se salta.
        if _mixta:
            # a) Agregados ABSOLUTOS: los de yfinance están en la divisa de
            #    reporte; los de TradingView en dólares. Se SUSTITUYEN (no se
            #    rellenan): el valor viejo existe, pero está en otra escala.
            for _k in _AGREGADOS_DIVISA:
                _nuevo = tv.get(_k)
                if _nuevo is not None:
                    result[_k] = _nuevo
            # b) Múltiplos que mezclan las dos divisas: se prefiere TradingView
            #    si es plausible. Si no lo es, quedan como estaban y el bloque
            #    de neutralización de más abajo los deja en None.
            for _k in _MULTIPLOS_DIVISA:
                _nuevo = tv.get(_k)
                if _nuevo is not None and _en_banda(_k, _nuevo):
                    result[_k] = _nuevo
            # c) Red de seguridad para el resto de múltiplos de la lista blanca
            #    (P/E y Forward P/E): solo si el actual está roto Y el de TV es
            #    plausible. En la práctica no se dispara, porque el P/E de
            #    yfinance ya viene bien en USD — está aquí por si acaso.
            for _k in _BANDAS_MULTIPLO:
                _nuevo = tv.get(_k)
                if (_nuevo is not None and not _en_banda(_k, result.get(_k))
                        and _en_banda(_k, _nuevo)):
                    result[_k] = _nuevo

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

    # ── Neutralización por divisa mixta ───────────────────────────────────
    # Lo que no se ha podido rescatar en USD se deja en None a propósito: la UI
    # pinta «—» y el prompt del agente dice «N/A». Un hueco honesto es mucho
    # mejor que un 46470 % de FCF Yield pintado en verde, o que un margen bruto
    # de 0.0 % en rojo cuando en realidad es un banco y el concepto no aplica.
    if _mixta:
        # a) Ceros ENVENENADOS de yfinance: para CIB grossMargins y
        #    operatingMargins llegan 0.0 mientras profitMargins sí tiene valor.
        #    Un 0.0 exacto junto a un beneficio positivo no existe en la
        #    práctica: es ausencia de dato disfrazada de cero.
        for _k in ("gross_margin_yf", "operating_margin_yf"):
            if result.get(_k) == 0.0:
                result[_k] = None
        # b) Múltiplos que siguen fuera de banda tras el rescate de TradingView.
        for _k in _BANDAS_MULTIPLO:
            if result.get(_k) is not None and not _en_banda(_k, result[_k]):
                result[_k] = None
        # c) EV/Revenue re-derivado de dos agregados que YA están ambos en USD
        #    (TradingView), en vez del enterpriseToRevenue contaminado de YF.
        if result.get("ev_revenue_yf") is None:
            try:
                _ev, _rev = result.get("enterprise_value_yf"), result.get("revenue_ttm")
                if _ev and _rev and float(_rev) > 0:
                    result["ev_revenue_yf"] = round(float(_ev) / float(_rev), 3)
            except Exception:
                pass

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
    # Tickers de CLASE: TradingView usa el PUNTO (BRK.B), no el guion que usa
    # yfinance (BRK-B). Sin esta variante la consulta salía vacía y en Render
    # el sector/industria de esas acciones se quedaba en "Unknown".
    for _tk in ([ticker.upper()] +
                ([ticker.upper().replace("-", ".")] if "-" in ticker else [])):
        _out = _tv_company_row(_tk)
        if _out:
            return _out
    return {}


def _tv_company_row(_tk: str) -> dict:
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
                # FIX: `current_ratio_quarterly` devuelve None SIEMPRE (medido
                # con la query real contra AAPL y KO) → el respaldo del Current
                # Ratio llevaba muerto desde que se escribió. El nombre válido
                # hoy es `current_ratio`.
                "debt_to_equity", "current_ratio",
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
                # ── Respaldos AMPLIADOS: agregados absolutos que TradingView
                # publica en USD también para los ADR (`currency` sale USD para
                # CIB). Cubren los campos que dependían SOLO de yfinance y que
                # en las extranjeras venían vacíos o en la divisa local.
                # Todas verificadas una a una contra AAPL y CIB.
                "currency",
                "enterprise_value_current", "total_debt", "ebitda",
                "free_cash_flow_ttm", "cash_f_operating_activities_ttm",
                "cash_n_short_term_invest_fq", "quick_ratio",
                "number_of_employees", "return_on_invested_capital",
                "price_52_week_high", "price_52_week_low",
            )
            .where(col("name") == _tk)
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
            "current_ratio_yf":    _f("current_ratio"),
            "quick_ratio_yf":      _f("quick_ratio"),
            # Agregados absolutos (en USD, también para los ADR)
            "ebitda_yf":           _f("ebitda"),
            "fcf_yf":              _f("free_cash_flow_ttm"),
            "ocf_yf":              _f("cash_f_operating_activities_ttm"),
            "total_cash_yf":       _f("cash_n_short_term_invest_fq"),
            "total_debt_yf":       _f("total_debt"),
            "enterprise_value_yf": _f("enterprise_value_current"),
            "employees":           _f("number_of_employees"),
            "52w_high":            _f("price_52_week_high"),
            "52w_low":             _f("price_52_week_low"),
            "roic_tv":             _f("return_on_invested_capital"),
            "tv_currency":         (str(row.get("currency", "") or "").upper() or None),
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


# ── Dividendo por acción, en dólares (informativo) ─────────────────────────

# Cadencia de pago → palabra en español para el tooltip.
_PERIODO_DIV = {1: "año", 2: "semestre", 4: "trimestre", 12: "mes"}


def _cadencia_desde_importes(anual, por_pago):
    """Nº de pagos al año a partir de (importe anual, importe de UN pago).

    Solo devuelve un número si el cociente cae MUY cerca de una cadencia real
    (1, 2, 4 o 12 pagos). Si no encaja devuelve None y el tooltip se queda solo
    con la cifra anual: preferimos no decir nada a inventar una cadencia.
    Medido: KO 2.12/0.53 = 4.0 ✓ · O 3.25/0.271 = 12.0 ✓ · CIB semestral ✓ ·
    ITUB 0.17/0.003 = 56.7 ✗ → sin detalle. NUNCA lanza."""
    try:
        if not anual or not por_pago or float(por_pago) <= 0:
            return None
        ratio = float(anual) / float(por_pago)
        for n in (1, 2, 4, 12):
            if abs(ratio - n) <= n * 0.15:
                return n
        return None
    except Exception:
        return None


def _div_plausible(anual, precio):
    """Filtro anti-basura: un dividendo por acción tiene que ser positivo y su
    yield implícito tiene que caber en la realidad (≤30%). Corta de raíz los
    importes que llegan en OTRA divisa — un dividendo en pesos contra un precio
    en dólares da un yield de miles por ciento. NUNCA lanza."""
    try:
        a = float(anual)
        if a <= 0 or a != a:
            return False
        p = float(precio or 0)
        if p > 0 and (a / p) > 0.30:
            return False
        return True
    except Exception:
        return False


def get_dividend_info(ticker: str, info: Optional[dict] = None) -> dict:
    """Dividendo ANUAL por acción, en dólares. INFORMATIVO: no entra en el
    scoring, no viaja al prompt de ningún agente y no modifica get_company_info.

    Devuelve SIEMPRE la misma forma:
        {"estado": "paga"|"no_paga"|"desconocido",
         "anual": float|None, "por_pago": float|None,
         "pagos_ano": int|None, "fuente": str}

    POR QUÉ TRES ESTADOS: la tile tiene que poder DISTINGUIR «la fuente
    respondió y esta empresa no reparte dividendo» (→ «No») de «no respondió
    nadie» (→ «—»). Con un 0 o un None a secas, TSLA y una acción con Yahoo
    caído se veían igual, que era justo el problema a evitar.

    CADENA (cada eslabón en su propio try; NUNCA lanza):
      a) yfinance `dividendRate` — la tasa anualizada vigente. Trae además
         `lastDividendValue`, de donde sale la cadencia REAL: es el único
         eslabón capaz de afirmar «paga mensual» (TradingView agrega por
         trimestre y para O —que paga cada mes— diría «trimestral»).
      b) TradingView `dps_common_stock_prim_issue_fy` — dividendo del último
         ejercicio cerrado. Comprobado: KO 2.04, AAPL 1.02, O 3.223, CIB 2.55,
         TSLA 0. Funciona con Yahoo bloqueado (Render), que es su razón de ser.
      c) Nasdaq `annualizedDividend` / `rows[].amount`. Va el ÚLTIMO y su 'N/A'
         NUNCA cuenta como «no paga»: medido, para NYSE (KO, CIB, NU) devuelve
         'N/A' y cero filas — interpretarlo haría que KO dijera «No».
      d) Histórico `.dividends` de yfinance: suma de los últimos 12 meses.

    El estado «no_paga» solo se afirma con una fuente que lo diga en POSITIVO:
    TradingView con dps == 0 Y `continuous_dividend_payout` == 0 (medido: 0
    años para TSLA/NU/BRK.B, 46 para KO). Nunca por ausencia de respuesta."""
    key = f"dividendo_{ticker}"
    cached = _load_cache(key, ttl_hours=TTL_FINANCIALS)   # 24 h
    if cached:
        return cached

    res = {"estado": "desconocido", "anual": None, "por_pago": None,
           "pagos_ano": None, "fuente": ""}
    precio = None
    no_paga_confirmado = False

    # a) yfinance — reutiliza el `info` ya descargado si el llamador lo pasa
    try:
        yi = info if (isinstance(info, dict) and info) else None
        if yi is None:
            crudo = _yt(ticker).info or {}
            rate     = crudo.get("dividendRate")
            ultimo   = crudo.get("lastDividendValue")
            trailing = crudo.get("trailingAnnualDividendRate")
            precio   = crudo.get("currentPrice") or crudo.get("regularMarketPrice")
            # «Respondió» exige PRUEBA de que el símbolo existe (un precio):
            # yfinance devuelve un dict NO vacío también para tickers
            # inexistentes, y sin esta condición un símbolo inventado se
            # declaraba «no paga» en vez de «desconocido».
            respondio = bool(precio)
        else:
            rate     = yi.get("dividend_rate_yf")
            ultimo   = yi.get("last_dividend_value_yf")
            trailing = yi.get("trailing_div_rate_yf")
            precio   = yi.get("current_price")
            respondio = bool(precio) and ("dividend_rate_yf" in yi or
                                          "trailing_div_rate_yf" in yi)

        anual = rate if _div_plausible(rate, precio) else None
        if anual is None and _div_plausible(trailing, precio):
            anual = trailing
        if anual is not None:
            res.update(estado="paga", anual=float(anual), fuente="yfinance")
            n = _cadencia_desde_importes(anual, ultimo)
            if n:
                res["por_pago"], res["pagos_ano"] = float(ultimo), n
        elif respondio and not rate and not trailing:
            # Respondió y no hay NINGUNA tasa → candidato a «no paga». No se
            # cierra aquí: se confirma con TradingView en (b).
            no_paga_confirmado = True
    except Exception:
        pass

    # b) TradingView — además es quien CONFIRMA el «no paga»
    if res["estado"] != "paga" or res["pagos_ano"] is None:
        try:
            from tradingview_screener import Query, col
            variantes = [str(ticker).upper()]
            if "-" in variantes[0]:
                variantes.append(variantes[0].replace("-", "."))
            for tk in variantes:
                _, df = (Query()
                         .select("name", "dps_common_stock_prim_issue_fy",
                                 "continuous_dividend_payout", "close")
                         .where(col("name") == tk).limit(1).get_scanner_data())
                if df is None or df.empty:
                    continue
                fila = df.iloc[0]

                def _f(clave):
                    try:
                        v = float(fila.get(clave))
                        return v if v == v else None      # NaN
                    except (TypeError, ValueError):
                        return None

                dps  = _f("dps_common_stock_prim_issue_fy")
                anos = _f("continuous_dividend_payout")
                px   = _f("close") or precio
                if res["estado"] != "paga" and _div_plausible(dps, px):
                    res.update(estado="paga", anual=float(dps),
                               fuente="TradingView")
                    # La cadencia NO se deriva de TradingView: agrega por
                    # trimestre y mentiría con un pagador mensual como O.
                if dps == 0.0 and not anos:
                    no_paga_confirmado = True
                break
        except Exception:
            pass

    # c) Nasdaq — reaprovecha el endpoint que ya usa data/events.py
    if res["estado"] != "paga":
        try:
            for tk in {str(ticker).upper(), str(ticker).upper().replace("-", ".")}:
                datos = _nasdaq_json(f"/api/quote/{tk}/dividends?assetclass=stocks")
                if not datos:
                    continue
                anual = _nasdaq_num(datos.get("annualizedDividend"))  # 'N/A' → None
                if anual is None:
                    filas = ((datos.get("dividends") or {}).get("rows") or [])
                    importes = [_nasdaq_num(f.get("amount")) for f in filas[:4]]
                    importes = [x for x in importes if x]
                    if len(importes) >= 4:
                        anual = sum(importes)
                if _div_plausible(anual, precio):
                    res.update(estado="paga", anual=float(anual), fuente="Nasdaq")
                    break
        except Exception:
            pass

    # d) Histórico de yfinance — último recurso, y el que mejor ve la cadencia
    #    real cuando `lastDividendValue` no vino.
    if res["estado"] != "paga" or res["pagos_ano"] is None:
        try:
            serie = _yt(ticker).dividends
            if serie is not None and len(serie) > 0:
                idx = serie.index
                idx = idx.tz_localize(None) if getattr(idx, "tz", None) else idx
                corte = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365)
                ult = serie[idx >= corte]
                if len(ult) > 0:
                    suma = float(ult.sum())
                    if res["estado"] != "paga" and _div_plausible(suma, precio):
                        res.update(estado="paga", anual=suma,
                                   fuente="yfinance histórico")
                    if res["pagos_ano"] is None and res["estado"] == "paga":
                        n = _cadencia_desde_importes(res["anual"], float(ult.iloc[-1]))
                        if n:
                            res["por_pago"], res["pagos_ano"] = float(ult.iloc[-1]), n
        except Exception:
            pass

    if res["estado"] != "paga" and no_paga_confirmado:
        res.update(estado="no_paga", fuente="yfinance/TradingView")

    # NUNCA se cachea un «desconocido»: un fallo puntual de red no puede
    # congelar el «—» durante 24 h (mismo criterio que el rescate del snapshot).
    if res["estado"] != "desconocido":
        _save_cache(key, res)
    return res


# ── Métricas financieras ───────────────────────────────────────────────────

def _get_financials_from_nasdaq(ticker: str) -> dict:
    """Estados financieros anuales vía Nasdaq, en el MISMO formato que
    get_financials(). Su valor está en que Nasdaq publica SIEMPRE en dólares,
    también para los ADR: para CIB devuelve los ingresos en USD mientras
    yfinance los da en pesos colombianos. NUNCA lanza; devuelve {} si falla.

    Unidades: las tablas vienen en MILES de USD — comprobado contra AAPL
    («Total Revenue $416,161,000» = 416,16 mil millones) → se multiplica ×1000.
    No hay fila de Free Cash Flow: se calcula como «Net Cash Flow-Operating» +
    «Capital Expenditures» (el capex ya viene en negativo en la tabla)."""
    out = {}
    try:
        datos = _nasdaq_json(f"/api/company/{ticker.upper()}/financials?frequency=1")
        if not datos:
            return out

        def _tabla(nombre):
            t = datos.get(nombre) or {}
            filas = {}
            for r in (t.get("rows") or []):
                filas[str(r.get("value1", "")).strip()] = [
                    r.get("value2"), r.get("value3"),
                    r.get("value4"), r.get("value5")]
            return filas, (t.get("headers") or {})

        inc, hdr = _tabla("incomeStatementTable")
        bal, _   = _tabla("balanceSheetTable")
        cf,  _   = _tabla("cashFlowTable")
        if not inc and not bal and not cf:
            return out

        def _serie(filas, etiqueta):
            v = filas.get(etiqueta)
            if not v:
                return None
            s = [(_nasdaq_num(x) * 1000.0) if _nasdaq_num(x) is not None else None
                 for x in v]
            return s if any(x is not None for x in s) else None

        def _uno(filas, etiqueta):
            s = _serie(filas, etiqueta)
            return s[0] if s else None

        for clave, filas, etiqueta in (
            ("revenue",             inc, "Total Revenue"),
            ("gross_profit",        inc, "Gross Profit"),
            ("operating_income",    inc, "Operating Income"),
            ("net_income",          inc, "Net Income"),
            ("operating_cash_flow", cf,  "Net Cash Flow-Operating"),
            ("capex",               cf,  "Capital Expenditures"),
        ):
            s = _serie(filas, etiqueta)
            if s:
                out[clave] = s

        ocf, capex = out.get("operating_cash_flow"), out.get("capex")
        if ocf and capex:
            out["free_cash_flow"] = [
                (o + c) if (o is not None and c is not None) else None
                for o, c in zip(ocf, capex)]

        for clave, etiqueta in (
            ("total_debt",          "Long-Term Debt"),
            ("cash",                "Cash and Cash Equivalents"),
            ("total_assets",        "Total Assets"),
            ("total_equity",        "Total Equity"),
            ("current_assets",      "Total Current Assets"),
            ("current_liabilities", "Total Current Liabilities"),
        ):
            v = _uno(bal, etiqueta)
            if v is not None:
                out[clave] = v

        anos = [str(hdr.get(k, ""))[-4:]
                for k in ("value2", "value3", "value4", "value5")]
        anos = [a for a in anos if a.isdigit()]
        if anos:
            out["fiscal_years"] = anos
        out["moneda"] = "USD"
        out["fuente_financials"] = "Nasdaq"
    except Exception:
        pass
    return out


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

    # ── Respaldo Nasdaq (siempre en USD) ──────────────────────────────────
    # DOS disparadores, los dos imposibles en una acción USA sana:
    #   · la empresa REPORTA en otra divisa → lo que trajo yfinance está en
    #     pesos/reales y NO sirve: se DESCARTA y se rehace desde Nasdaq (si no
    #     se descartara, los ingresos seguirían en COP y mezclados con el market
    #     cap en USD producen el FCF Yield de 46470 %);
    #   · yfinance no trajo NADA de ingresos (Yahoo bloqueado, caso Render).
    # Para AAPL/KO/MSFT la divisa coincide y `revenue` viene lleno → el bloque
    # entero se salta y el resultado es byte a byte el de siempre.
    # get_company_info(ticker) se llama SIEMPRE antes que get_financials (tanto
    # en el agente como en la UI), así que su caché está caliente y esta lectura
    # no dispara ni una petición de red extra.
    try:
        _inf = _load_cache(f"info_{ticker}", ttl_hours=TTL_COMPANY_INFO) or {}
        _ajena = (bool(_inf.get("financial_currency")) and
                  str(_inf["financial_currency"]).upper() != "USD")
        _rev = result.get("revenue") or []
        _sin_ingresos = (not _rev) or all(v is None for v in _rev)

        if _ajena or _sin_ingresos:
            nd = _get_financials_from_nasdaq(ticker)
            if nd:
                if _ajena:
                    for _k in ("revenue", "gross_profit", "operating_income",
                               "net_income", "ebitda", "free_cash_flow",
                               "operating_cash_flow", "capex", "total_debt",
                               "cash", "total_assets", "total_equity",
                               "current_assets", "current_liabilities",
                               "fiscal_years"):
                        result.pop(_k, None)
                for _k, _v in nd.items():
                    if _k not in result or result.get(_k) in (None, [], {}):
                        result[_k] = _v
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

    # ROIC proxy — necesita beneficio operativo Y capital invertido. Las
    # empresas donde el beneficio operativo no viene (bancos y buena parte de
    # las extranjeras) se quedaban sin ROIC. TradingView lo publica calculado y
    # ya en porcentaje, así que se usa como respaldo. Solo se rellena si el
    # cálculo propio no salió: nunca pisa el valor de siempre, y para las
    # acciones USA `roic_tv` ni existe (TradingView no llega a llamarse).
    invested_capital = (equity or 0) + debt - cash
    if safe(oi, 0) and invested_capital and invested_capital > 0:
        ratios["roic"] = safe(oi, 0) * (1 - 0.21) / invested_capital * 100
    elif info.get("roic_tv") is not None:
        ratios["roic"] = float(info["roic_tv"])

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


def _nasdaq_json(path: str, _intentos: int = 2) -> Optional[dict]:
    """GET a la API pública de Nasdaq (api.nasdaq.com). Nasdaq cubre TODAS las
    acciones de NASDAQ y NYSE y no rate-limita las IPs de datacenter como sí
    hace Yahoo. Devuelve el dict 'data' de la respuesta, o None. NUNCA lanza.

    REINTENTO: Nasdaq corta esporádicamente una petición cuando se encadenan
    varias seguidas (insiders → institucionales → short interest, todas en el
    mismo render). El `except: pass` de los llamadores convertía ese fallo
    transitorio en un «esta empresa no tiene insiders» silencioso. Se reintenta
    UNA vez y SOLO ante fallo real —excepción o 403/429/5xx—, nunca ante un 200
    con datos vacíos, que es una respuesta legítima (para NYSE el endpoint de
    dividendos responde 200 y vacío, y reintentarlo sería tiempo tirado). El
    segundo intento usa un timeout más corto para que el peor caso no dispare
    el tiempo de carga: 15 s + 0,8 s + 8 s en vez de 30 s."""
    url = f"https://api.nasdaq.com{path}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    intentos = max(1, int(_intentos))
    for intento in range(intentos):
        try:
            resp = requests.get(url, headers=headers,
                                timeout=15 if intento == 0 else 8)
            if resp.status_code == 200:
                payload = resp.json()
                return payload.get("data") if isinstance(payload, dict) else None
            if resp.status_code not in (403, 429, 500, 502, 503, 504):
                return None      # 404 y demás: no hay nada que reintentar
        except Exception:
            pass
        if intento + 1 < intentos:
            time.sleep(0.8)
    return None


# Códigos de operación del Form 4 → el vocabulario que YA usa la app
# ("compra"/"venta"/"concesión"/"donación"/"otra" gobiernan el color de la
# tabla en dashboard/app.py). P = compra en mercado abierto, S = venta,
# A = concesión de acciones, G = donación; el resto (M ejercicio de opciones,
# F retención fiscal, D entrega al emisor, C conversión) va a "otra".
_SEC_CODIGO_TIPO = {"P": "compra", "S": "venta", "A": "concesión", "G": "donación"}


def _get_insiders_from_sec(ticker: str, max_formularios: int = 12) -> dict:
    """ÚLTIMO eslabón de la cadena de insiders: los Form 4 que los directivos
    presentan a la SEC.

    POR QUÉ HACE FALTA. Para las empresas extranjeras ni yfinance ni Nasdaq
    tienen insiders: medido con CIB, yfinance devuelve lista vacía y Nasdaq
    'totalRecords: 0', así que la sección de la UI desaparecía en silencio.
    Pero la SEC SÍ los tiene: 59 Form 4 presentados. Esta función los lee del
    origen.

    Devuelve {insider_transactions, recent_insider_buys, recent_insider_sells}
    con EXACTAMENTE el mismo contrato que consume la tabla de dashboard/app.py:
    cada operación es {date, insider, position, shares, value, type, text}.
    Si tampoco aquí hay nada devuelve {} y la sección sigue sin aparecer,
    igual que hoy.

    Coste: 1 petición al índice + hasta `max_formularios` XML pequeños, con una
    pausa de 0,12 s entre medias para respetar el límite de 10 peticiones/s de
    la SEC. Solo se llega aquí cuando los DOS eslabones previos vinieron
    vacíos, o sea en el camino que hoy no produce absolutamente nada.
    NUNCA lanza."""
    resultado = {}
    try:
        import xml.etree.ElementTree as ET
        # Import diferido A PROPÓSITO: data/events.py importa de este módulo,
        # así que un import arriba crearía una dependencia circular.
        from data.events import _sec_cik, _SEC_UA

        cik = _sec_cik(ticker)
        if not cik:
            return resultado

        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=_SEC_UA, timeout=15)
        if r.status_code != 200:
            return resultado
        rec = ((r.json() or {}).get("filings") or {}).get("recent") or {}
        formas = rec.get("form") or []
        accs   = rec.get("accessionNumber") or []
        docs   = rec.get("primaryDocument") or []

        indices = [i for i, f in enumerate(formas)
                   if str(f).upper() in ("4", "4/A")][:max_formularios]
        if not indices:
            return resultado

        cik_int = str(int(cik))       # la URL del archivo usa el CIK sin ceros
        txns, compras, ventas = [], 0, 0

        for i in indices:
            if len(txns) >= 20:
                break
            try:
                acc = str(accs[i]).replace("-", "")
                # primaryDocument puede venir como 'xslF345X06/wk-form4_….xml'
                # (la versión renderizada); el XML crudo es el mismo nombre sin
                # la carpeta xsl delante.
                doc = str(docs[i]).split("/")[-1]
                url = (f"https://www.sec.gov/Archives/edgar/data/"
                       f"{cik_int}/{acc}/{doc}")
                rr = requests.get(url, headers=_SEC_UA, timeout=15)
                if rr.status_code != 200:
                    continue
                raiz = ET.fromstring(rr.text)

                nombre = (raiz.findtext(".//rptOwnerName") or "").title()
                cargo = (raiz.findtext(".//officerTitle") or "").strip()
                if not cargo:
                    # Los Form 4 extranjeros suelen dejar officerTitle vacío:
                    # el cargo se deduce de las casillas de relación.
                    rel = raiz.find(".//reportingOwnerRelationship")
                    papeles = []
                    if rel is not None:
                        for etiqueta, campo in (("Director", "isDirector"),
                                                ("Directivo", "isOfficer"),
                                                ("Accionista 10%", "isTenPercentOwner")):
                            if str(rel.findtext(campo) or "0").lower() in ("1", "true"):
                                papeles.append(etiqueta)
                    cargo = ", ".join(papeles)

                for etiqueta in ("nonDerivativeTransaction", "derivativeTransaction"):
                    for tr in raiz.iter(etiqueta):
                        codigo = (tr.findtext(".//transactionCode") or "").strip().upper()
                        tipo = _SEC_CODIGO_TIPO.get(codigo, "otra")
                        try:
                            acciones = float(tr.findtext(".//transactionShares/value") or 0)
                        except (TypeError, ValueError):
                            acciones = 0.0
                        try:
                            precio = float(tr.findtext(".//transactionPricePerShare/value") or 0)
                        except (TypeError, ValueError):
                            precio = 0.0
                        if tipo == "compra":
                            compras += 1
                        elif tipo == "venta":
                            ventas += 1
                        txns.append({
                            "date":     (tr.findtext(".//transactionDate/value") or "")[:10],
                            "insider":  nombre,
                            "position": cargo,
                            "shares":   acciones,
                            "value":    acciones * precio,
                            "type":     tipo,
                            "text":     ("Form 4 · código %s" % codigo) if codigo else "Form 4",
                        })
            except Exception:
                continue
            time.sleep(0.12)

        if txns:
            resultado["insider_transactions"] = txns[:20]
            resultado["recent_insider_buys"]  = compras
            resultado["recent_insider_sells"] = ventas
    except Exception:
        pass
    return resultado


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

    # Tercer y último eslabón: la SEC (Form 4). Solo se intenta si los DOS
    # anteriores vinieron vacíos — el caso de las empresas extranjeras (CIB),
    # donde ni yfinance ni Nasdaq tienen insiders pero la SEC sí. Para
    # AAPL/KO/MSFT esta condición es falsa y la SEC ni se toca. Si aquí
    # tampoco hay nada, la sección de la UI simplemente no aparece, exactamente
    # igual que hoy.
    if not result.get("insider_transactions"):
        sec = _get_insiders_from_sec(ticker)
        if sec.get("insider_transactions"):
            result["insider_transactions"] = sec["insider_transactions"]
            result["recent_insider_buys"] = sec.get("recent_insider_buys", 0)
            result["recent_insider_sells"] = sec.get("recent_insider_sells", 0)

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
#
# get_news era la ÚNICA función de datos del proyecto sin cadena de respaldo:
# dependía solo de yfinance, que Yahoo bloquea desde IPs de datacenter. En la
# nube se quedaba vacía y tanto Sentimiento como Catalizadores opinaban a ciegas.
# Estas tres fuentes cubren ese hueco. Todas devuelven EXACTAMENTE el mismo
# formato de dict que la ruta de yfinance (title/publisher/link/date/age_hours/
# freshness), así que nada de lo que ya consumía noticias tiene que cambiar.

def _freshness(age_hours: float) -> str:
    """Etiqueta de frescura — misma escala que usa la ruta de yfinance."""
    return ("🔥 HOY" if age_hours < 24 else
            "⚡ Esta semana" if age_hours < 168 else
            "📅 Antigua")


def _news_item(title, publisher, link, pub_dt, now) -> Optional[dict]:
    """Normaliza una noticia al formato común. None si no hay titular."""
    if not title:
        return None
    pub_dt = pub_dt or now
    age_hours = (now - pub_dt).total_seconds() / 3600
    if age_hours < 0:
        age_hours = 0.0
    return {
        "title":     str(title).strip(),
        "publisher": str(publisher or "").strip(),
        "link":      str(link or "").strip(),
        "date":      pub_dt.strftime("%Y-%m-%d %H:%M"),
        "age_hours": round(age_hours, 1),
        "freshness": _freshness(age_hours),
    }


def _parse_rfc822(s):
    """'Tue, 28 Jul 2026 14:03:00 GMT' → datetime naive. None si no se puede."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(str(s))
        return dt.replace(tzinfo=None) if dt else None
    except Exception:
        return None


def _news_from_rss(url: str, publisher_por_defecto: str, max_items: int) -> list:
    """Lee un feed RSS con la biblioteca estándar (sin dependencias nuevas).
    NUNCA lanza: ante cualquier problema devuelve []."""
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        })
        if resp.status_code != 200 or not resp.text:
            return []
        raiz = ET.fromstring(resp.content)
        now = datetime.now()
        salida = []
        for item in raiz.iter("item"):
            titulo = (item.findtext("title") or "").strip()
            enlace = (item.findtext("link") or "").strip()
            fuente = (item.findtext("source") or "").strip() or publisher_por_defecto
            pub_dt = _parse_rfc822(item.findtext("pubDate"))
            noticia = _news_item(titulo, fuente, enlace, pub_dt, now)
            if noticia:
                salida.append(noticia)
            if len(salida) >= max_items:
                break
        return salida
    except Exception:
        return []


def _get_news_from_nasdaq(ticker: str, max_items: int = 15) -> list:
    """Respaldo #1: API pública de Nasdaq (no rate-limita IPs de datacenter)."""
    try:
        now = datetime.now()
        for tk in {ticker.upper(), ticker.upper().replace("-", ".")}:
            datos = _nasdaq_json(
                f"/api/news/topic/articlebysymbol?q={tk}|stocks&offset=0&limit={max_items}")
            filas = (datos or {}).get("rows") or []
            if not filas:
                continue
            salida = []
            for fila in filas:
                pub_dt = None
                crudo = fila.get("created") or fila.get("publisher_date")
                for formato in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
                    try:
                        pub_dt = datetime.strptime(str(crudo)[:19], formato)
                        break
                    except (ValueError, TypeError):
                        continue
                enlace = fila.get("url") or ""
                if enlace and enlace.startswith("/"):
                    enlace = f"https://www.nasdaq.com{enlace}"
                noticia = _news_item(fila.get("title"), fila.get("publisher") or "Nasdaq",
                                     enlace, pub_dt, now)
                if noticia:
                    salida.append(noticia)
            if salida:
                return salida[:max_items]
        return []
    except Exception:
        return []


def _get_news_from_yahoo_rss(ticker: str, max_items: int = 15) -> list:
    """Respaldo #2: RSS de Yahoo Finance. Va por una infraestructura distinta a
    la API que yfinance usa, así que suele responder cuando aquella está cerrada."""
    return _news_from_rss(
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker.upper()}"
        f"&region=US&lang=en-US",
        "Yahoo Finance", max_items)


def _get_news_from_google_rss(ticker: str, max_items: int = 15) -> list:
    """Respaldo #3: Google News. Último recurso, pero prácticamente siempre
    responde. Se acota la consulta a la acción para no traer ruido homónimo."""
    consulta = f"{ticker.upper()}+stock+OR+shares"
    return _news_from_rss(
        f"https://news.google.com/rss/search?q={consulta}&hl=en-US&gl=US&ceid=US:en",
        "Google News", max_items)


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

    # Cadena de respaldo — mismo patrón que get_earnings_data y get_holders_data.
    # Solo entra en juego si yfinance no trajo NADA (en Render, siempre), así que
    # donde ya había noticias sale exactamente lo mismo que antes.
    if not result:
        for respaldo in (_get_news_from_nasdaq,
                         _get_news_from_yahoo_rss,
                         _get_news_from_google_rss):
            try:
                result = respaldo(ticker, max_items)
            except Exception:
                result = []
            if result:
                result.sort(key=lambda x: x.get("age_hours", 9999))
                result = result[:max_items]
                break

    # NO cachear un vacío: un fallo transitorio de TODAS las fuentes no debe
    # congelar "sin noticias" durante todo el TTL.
    if result:
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


def get_live_snapshot_cached(tickers: list[str] = None) -> dict:
    """SOLO el caché del snapshot (cero red, cero espera). Para elementos
    decorativos como el ticker-tape del inicio: si aún no hay datos (primer
    arranque), devuelve {} y el tape pinta solo los símbolos. NUNCA lanza."""
    try:
        if tickers is None:
            tickers = POPULAR_TICKERS
        key = f"snapshot_{'_'.join(sorted(tickers))[:80]}"
        return _load_cache(key, ttl_hours=TTL_SNAPSHOT) or {}
    except Exception:
        return {}


def _snapshot_rescue_ticker(ticker: str):
    """Rescate INDIVIDUAL de un ticker que faltó en el snapshot en lote.

    Existe porque un fallo transitorio de Yahoo con UN símbolo dejaba su tile
    del inicio vacía ("—") y, peor, el hueco se CACHEABA durante todo el TTL
    (visto en producción con AAPL: las otras 11 cargaban y esa no). Cadena:

      a) yfinance individual con velas de 1h — los fallos del lote suelen ser
         por símbolo, y en solitario casi siempre responde (misma calidad:
         precio fresco + sparkline intradía).
      b) Nasdaq histórico diario — funciona con Yahoo bloqueado (Render).
         El precio puede ser el cierre de ayer y el sparkline diario: mejor
         un dato de ayer que un hueco.

    Devuelve el dict con la MISMA forma que el snapshot, o None. NUNCA lanza."""
    # a) yfinance individual (intradía)
    try:
        df = _yt(ticker).history(period="5d", interval="1h")
        if df is not None and not df.empty and "Close" in df.columns:
            closes = df["Close"].dropna()
            if len(closes) >= 2:
                price = float(closes.iloc[-1])
                daily_last = closes.groupby(
                    [d.date() for d in closes.index]).last()
                prev = (float(daily_last.iloc[-2]) if len(daily_last) >= 2
                        else float(closes.iloc[0]))
                if prev > 0:
                    return {
                        "price": price,
                        "change_pct": (price - prev) / prev * 100,
                        "change_abs": price - prev,
                        "closes": [round(float(x), 4)
                                   for x in closes.tail(40).tolist()],
                    }
    except Exception:
        pass
    # b) Nasdaq diario (infalible en datacenter)
    try:
        df = _get_price_history_from_nasdaq(ticker, period="1mo")
        if df is not None and not df.empty and "Close" in df.columns:
            closes = df["Close"].dropna()
            if len(closes) >= 2:
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                if prev > 0:
                    return {
                        "price": price,
                        "change_pct": (price - prev) / prev * 100,
                        "change_abs": price - prev,
                        "closes": [round(float(x), 4)
                                   for x in closes.tail(10).tolist()],
                    }
    except Exception:
        pass
    return None


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
        # interval="1h" (antes "1d"): la MISMA llamada trae ~35 velas por
        # ticker → el sparkline tiene textura intradía real (micro subidas y
        # bajadas) en vez de 5 puntos planos. El precio y el % diario se
        # calculan igual que antes: último cierre vs cierre del día previo.
        data = yf.download(tickers, period="5d", interval="1h", auto_adjust=True,
                          progress=False, group_by="ticker", threads=True)
        for ticker in tickers:
            try:
                if len(tickers) > 1 and ticker in data.columns.get_level_values(0):
                    df = data[ticker].dropna()
                else:
                    df = data.dropna()
                if df.empty or len(df) < 2:
                    continue
                closes = df["Close"]
                price = float(closes.iloc[-1])
                # Cierre del día ANTERIOR (igual que con velas diarias)
                daily_last = closes.groupby(
                    [d.date() for d in closes.index]).last()
                prev = (float(daily_last.iloc[-2]) if len(daily_last) >= 2
                        else float(closes.iloc[0]))
                change_pct = (price - prev) / prev * 100 if prev > 0 else 0
                result[ticker] = {
                    "price": price,
                    "change_pct": change_pct,
                    "change_abs": price - prev,
                    # Serie intradía 5d para el sparkline de las tiles.
                    # Aditivo y retrocompatible: los lectores usan .get("closes")
                    # y un caché viejo sin la clave caduca solo en ≤3 min.
                    "closes": [round(float(x), 4)
                               for x in closes.tail(40).tolist()],
                }
            except Exception:
                continue
    except Exception:
        pass

    # ── Rescate por ticker: que un fallo puntual del lote (o el bloqueo de
    # Yahoo en cloud) JAMÁS deje una tile vacía ni se cachee el hueco. Los
    # ausentes se recuperan EN PARALELO (el coste es el más lento, no la suma).
    faltantes = [t for t in tickers if t not in result]
    if faltantes:
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(6, len(faltantes))) as ex:
                for t, rec in zip(faltantes,
                                  ex.map(_snapshot_rescue_ticker, faltantes)):
                    if rec:
                        result[t] = rec
        except Exception:
            pass

    # Último recurso: el registro previo aunque su TTL haya caducado — un
    # precio de hace unos minutos es mejor que un hueco, y el TTL corto (3 min)
    # garantiza que se reintenta enseguida de todas formas.
    if len(result) < len(tickers):
        try:
            viejo_snap = _load_cache(key, ttl_hours=24) or {}
            for t in tickers:
                if t not in result and isinstance(viejo_snap.get(t), dict):
                    result[t] = viejo_snap[t]
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

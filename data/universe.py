"""
Universo de acciones para el screener. Usa el S&P500 completo + NASDAQ-100
obtenido de Wikipedia (sin API key). Con caché local de 24h.
"""
import json
import time
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "universe.json"


def get_sp500_tickers() -> list[str]:
    """Descarga los tickers del S&P500 de Wikipedia."""
    if CACHE_FILE.exists() and (time.time() - CACHE_FILE.stat().st_mtime) < 86400:
        return json.loads(CACHE_FILE.read_text())

    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(tickers))
        return tickers
    except Exception:
        return _fallback_tickers()


def get_nasdaq100_tickers() -> list[str]:
    """Top NASDAQ-100 tickers."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for t in tables:
            if "Ticker" in t.columns:
                return t["Ticker"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        pass
    return []


def get_full_universe() -> list[str]:
    """Universo del scan = NASDAQ-100 (las acciones más relevantes para retail).

    Decisión: reducimos de ~600 (S&P500 + NASDAQ-100) a ~100 porque Yahoo
    Finance rate-limita agresivamente las IPs de cloud providers (AWS, donde
    corre Streamlit Cloud). Con ~100 tickers el scan es confiable y rápido,
    sin perder cobertura de las acciones que la gente realmente sigue.
    Si en el futuro quieres scanear el universo completo, fallback a
    `_fallback_tickers()` o cambia esta función para concatenar S&P500."""
    ndx = get_nasdaq100_tickers()
    if ndx and len(ndx) >= 50:
        return ndx
    # Fallback estático si Wikipedia falla
    return _fallback_tickers()


def _fallback_tickers() -> list[str]:
    """Lista de respaldo con las 100 acciones más relevantes."""
    return [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "BRK-B", "JPM",
        "V", "UNH", "XOM", "LLY", "AVGO", "MA", "JNJ", "PG", "HD", "MRK",
        "COST", "ABBV", "CVX", "WMT", "BAC", "CRM", "NFLX", "AMD", "ACN", "LIN",
        "TMO", "ORCL", "MCD", "ABT", "DHR", "TXN", "ADBE", "QCOM", "CSCO", "VZ",
        "CAT", "AMGN", "PFE", "INTU", "IBM", "NOW", "GE", "UBER", "AXP", "SPGI",
        "HON", "MS", "RTX", "ISRG", "BLK", "BKNG", "GS", "AMAT", "LRCX", "PLD",
        "SYK", "T", "REGN", "VRTX", "DE", "PANW", "ADI", "KLAC", "SNPS", "CDNS",
        "MELI", "MU", "CRWD", "APP", "PLTR", "SHOP", "COIN", "SQ", "DDOG", "ZS",
        "NET", "SNOW", "TWLO", "OKTA", "CFLT", "PATH", "U", "RBLX", "HOOD", "AFRM",
        "RIVN", "LCID", "NIO", "XPEV", "LI", "SMCI", "ARM", "ASML", "TSM", "SAMSF",
    ]

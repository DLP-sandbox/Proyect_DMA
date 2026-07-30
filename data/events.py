"""
Catalizadores y eventos — CAPA 1 (red, con respaldos) + agregador.

QUÉ RESUELVE
------------
La sección de Catalizadores solo veía earnings. Aquí se recogen los OTROS
eventos que mueven una acción:

  · Eventos FUTUROS   → agenda: earnings, ex-dividendo y pago, conferencias y
                        lanzamientos del calendario estático (WWDC, GTC, I/O…).
  · Hechos RECIENTES  → lo que la empresa ya ha comunicado oficialmente a la SEC:
                        contratos materiales, compras/ventas de activos, cambios
                        en la directiva, reestructuraciones…

PRINCIPIO DE DISEÑO: NUNCA COLGARSE, NUNCA QUEDARSE VACÍO
---------------------------------------------------------
1. La CAPA 0 (`data/event_calendar.py`) no usa red y siempre produce algo. Es el
   suelo: aunque caiga Internet entero, la agenda tiene contenido.
2. Cada fuente de red va aislada en su propia función que NUNCA lanza y SIEMPRE
   lleva `timeout`. El fallo de una no afecta a las demás.
3. Las fuentes se piden EN PARALELO, así el coste en tiempo es el del timeout
   más lento (~8 s), no la suma.
4. Se cachea en disco (TTL 6 h) para que abrir la pestaña sea instantáneo, pero
   NUNCA se cachea un resultado vacío: un fallo puntual no puede congelar
   "sin eventos" durante horas (mismo criterio que `get_earnings_data`).

COBERTURA DE LOS DIVIDENDOS (comprobado en vivo)
------------------------------------------------
Ninguna fuente sola cubre todo el mercado, por eso se encadenan:
  · TradingView `dividend_ex_date_upcoming` → da la fecha FUTURA y funciona en
    NYSE (KO 2026-09-15, MCD 2026-09-01), pero no siempre en NASDAQ.
  · Nasdaq `/api/quote/{T}/dividends` → cubre los listados en NASDAQ (AAPL) y
    devuelve vacío para NYSE.
  · Si solo se conoce el ÚLTIMO ex-dividendo, se proyecta el siguiente con la
    cadencia observada en el histórico y se marca como estimado.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import requests

from data.market_data import _load_cache, _save_cache, _nasdaq_json
from data.event_calendar import (
    proximos_eventos_estaticos,
    TIPO_EARNINGS, TIPO_DIVIDENDO, TIPO_ACCIONISTA,
)


TTL_EVENTS = 6.0          # horas de caché del resultado agregado
HORIZONTE_DIAS = 270      # ventana de la agenda (~9 meses)
_TIMEOUT = 8              # segundos por petición

# La SEC exige identificarse con un contacto en cada petición. Se usa un correo
# genérico del proyecto (no uno personal), tal y como se decidió.
_SEC_UA = {
    "User-Agent": "DLP Market Analyzer contacto@dlp-analyzer.app",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


# ── Traducción de los códigos de ítem del formulario 8-K ──────────────────
# Un 8-K es el parte de "hecho relevante" de la SEC. Su código de ítem dice
# EXACTAMENTE qué pasó, sin tener que leer el documento ni pasar por la IA.
_ITEMS_8K = {
    "1.01": ("Contrato material firmado", "La empresa ha firmado un acuerdo importante (cliente, socio o proveedor)."),
    "1.02": ("Contrato material terminado", "Se ha cancelado o vencido un acuerdo importante."),
    "1.03": ("Procedimiento concursal", "La empresa ha entrado en un proceso de quiebra o suspensión de pagos."),
    "1.05": ("Incidente de ciberseguridad", "Se ha comunicado un incidente de seguridad con impacto material."),
    "2.01": ("Compra o venta de activos", "Operación corporativa: adquisición o desinversión relevante."),
    "2.02": ("Publicación de resultados", "Resultados trimestrales o anuales comunicados oficialmente."),
    "2.03": ("Nueva deuda relevante", "La empresa ha asumido una obligación financiera importante."),
    "2.04": ("Vencimiento anticipado de deuda", "Se ha acelerado una obligación financiera."),
    "2.05": ("Plan de reestructuración", "Costes por reorganización, cierres o despidos."),
    "2.06": ("Deterioro de activos", "Se ha reconocido una pérdida de valor en el balance."),
    "3.01": ("Aviso sobre la cotización", "Incumplimiento de los requisitos de permanencia en el mercado."),
    "3.02": ("Emisión de acciones no registrada", "Ampliación de capital fuera de mercado (dilución)."),
    "4.01": ("Cambio de auditor", "La empresa ha cambiado de firma auditora."),
    "4.02": ("Estados financieros no fiables", "La empresa avisa de que no se debe confiar en cuentas ya publicadas."),
    "5.01": ("Cambio de control", "Ha cambiado quién controla la compañía."),
    "5.02": ("Cambio en la directiva", "Nombramiento o salida de consejeros o altos directivos."),
    "5.03": ("Cambio de estatutos", "Modificación de los estatutos o del ejercicio fiscal."),
    "5.07": ("Votación de accionistas", "Resultados de la votación en la junta de accionistas."),
    "7.01": ("Comunicación al mercado", "Información divulgada al mercado (Reg FD)."),
    "8.01": ("Otro hecho relevante", "Comunicado que la empresa considera importante para el inversor."),
    "9.01": ("Documentos anexos", "Anexos que acompañan a otro hecho comunicado."),
}

# Ítems que por sí solos no cuentan nada (son anexos o el propio reporte de
# resultados, que ya aparece en la agenda por su cuenta).
_ITEMS_IGNORADOS = {"9.01"}

# Formularios SIN código de ítem que también son hechos relevantes.
# CLAVE para la cobertura internacional: las empresas extranjeras (NU, ASML,
# TSM…) NO presentan 8-K sino 6-K, así que sin esto se quedaban con cero hechos.
# El 6-K no viene clasificado, de modo que se etiqueta de forma honesta —sin
# inventar de qué trata— y se limita a unos pocos para no inundar la sección.
_FORMAS_RELEVANTES = {
    "6-K":  ("Comunicación oficial al mercado", "Hecho relevante presentado ante la SEC por una empresa extranjera (resultados, operaciones o anuncios corporativos)."),
    "20-F": ("Informe anual (empresa extranjera)", "Cuentas anuales auditadas y factores de riesgo del ejercicio."),
    "10-K": ("Informe anual", "Cuentas anuales auditadas y factores de riesgo del ejercicio."),
    "S-1":  ("Registro de nueva emisión", "La empresa registra valores para colocarlos en el mercado (posible dilución)."),
    "424B5": ("Colocación de valores", "Emisión de acciones o deuda ya en curso (posible dilución)."),
}
_MAX_POR_FORMA = 4      # tope por tipo de formulario sin clasificar (6-K…)


def _hoy():
    return date.today()


def _iso(d):
    return d.isoformat() if d else None


def _parse_fecha_us(s):
    """'05/11/2026' → date. None si no se puede."""
    try:
        return datetime.strptime(str(s).strip(), "%m/%d/%Y").date()
    except (ValueError, TypeError):
        return None


def _parse_iso(s):
    try:
        return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _evento(fecha, titulo, tipo, desc="", fuente="", estimada=False):
    """Construye una entrada de agenda. None si la fecha no es válida o pasada."""
    if not fecha:
        return None
    hoy = _hoy()
    if fecha < hoy:
        return None
    return {
        "fecha":    fecha.isoformat(),
        "dias":     (fecha - hoy).days,
        "titulo":   titulo,
        "tipo":     tipo,
        "desc":     desc,
        "fuente":   fuente,
        "estimada": bool(estimada),
    }


# ── SEC EDGAR ─────────────────────────────────────────────────────────────

def _sec_cik(ticker):
    """Ticker → CIK con ceros a la izquierda (10 dígitos). None si no está.
    El mapa completo (~10 400 empresas) se cachea 7 días: es un fichero estable."""
    try:
        tk = str(ticker or "").upper().strip()
        if not tk:
            return None
        mapa = _load_cache("sec_cik_map", ttl_hours=24 * 7)
        if not mapa:
            resp = requests.get("https://www.sec.gov/files/company_tickers.json",
                                headers=_SEC_UA, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return None
            crudo = resp.json() or {}
            mapa = {}
            for fila in crudo.values():
                sim = str(fila.get("ticker", "")).upper()
                if sim:
                    mapa[sim] = str(fila.get("cik_str", "")).zfill(10)
            if mapa:
                _save_cache("sec_cik_map", mapa)
        # BRK-B en la app ↔ BRK-B en la SEC (usa guion), pero se prueban ambos
        for variante in (tk, tk.replace(".", "-"), tk.replace("-", ".")):
            if variante in mapa:
                return mapa[variante]
        return None
    except Exception:
        return None


def _sec_hechos_relevantes(ticker):
    """Hechos comunicados a la SEC en los últimos ~180 días, ya traducidos.

    Devuelve {"hechos": [...], "agenda": [...]}: los 8-K van a `hechos`
    (pasado) y de la fecha del DEF 14A se estima la próxima junta anual, que sí
    es un evento futuro. NUNCA lanza."""
    vacio = {"hechos": [], "agenda": []}
    try:
        cik = _sec_cik(ticker)
        if not cik:
            return vacio
        resp = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                            headers=_SEC_UA, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return vacio
        recientes = ((resp.json() or {}).get("filings") or {}).get("recent") or {}

        formas  = recientes.get("form") or []
        fechas  = recientes.get("filingDate") or []
        items   = recientes.get("items") or [""] * len(formas)
        hoy = _hoy()
        corte = hoy - timedelta(days=180)

        hechos, agenda = [], []
        ultimo_def14a = None
        contador_forma = {}

        for i, forma in enumerate(formas):
            fecha = _parse_iso(fechas[i]) if i < len(fechas) else None
            if not fecha:
                continue

            if forma == "DEF 14A" and ultimo_def14a is None:
                ultimo_def14a = fecha

            if fecha < corte:
                continue

            if forma == "8-K":
                codigos = [c.strip() for c in str(items[i] if i < len(items) else "").split(",")]
                for codigo in codigos:
                    if not codigo or codigo in _ITEMS_IGNORADOS or codigo not in _ITEMS_8K:
                        continue
                    titulo, desc = _ITEMS_8K[codigo]
                    hechos.append({
                        "fecha":  fecha.isoformat(),
                        "dias":   (hoy - fecha).days,
                        "titulo": titulo,
                        "desc":   desc,
                        "codigo": codigo,
                        "fuente": "SEC",
                    })
            elif forma in _FORMAS_RELEVANTES:
                # Sin código de ítem: se limita el número para que no inunde
                # (una empresa extranjera puede presentar decenas de 6-K).
                contador_forma[forma] = contador_forma.get(forma, 0) + 1
                if contador_forma[forma] > _MAX_POR_FORMA:
                    continue
                titulo, desc = _FORMAS_RELEVANTES[forma]
                hechos.append({
                    "fecha":  fecha.isoformat(),
                    "dias":   (hoy - fecha).days,
                    "titulo": titulo,
                    "desc":   desc,
                    "codigo": forma,
                    "fuente": "SEC",
                })

        # La junta anual se celebra con una regularidad muy alta: el aviso de
        # convocatoria (DEF 14A) del año pasado marca la ventana del próximo.
        if ultimo_def14a:
            try:
                proxima = ultimo_def14a.replace(year=ultimo_def14a.year + 1)
            except ValueError:      # 29 de febrero
                proxima = ultimo_def14a + timedelta(days=365)
            ev = _evento(proxima, "Junta anual de accionistas", TIPO_ACCIONISTA,
                         "Ventana estimada a partir de la convocatoria del año anterior "
                         "registrada en la SEC.", "SEC", estimada=True)
            if ev and ev["dias"] <= HORIZONTE_DIAS:
                agenda.append(ev)

        # Los más recientes primero, y sin repetir el mismo tipo de hecho
        hechos.sort(key=lambda h: h["fecha"], reverse=True)
        unicos, vistos = [], set()
        for h in hechos:
            clave = (h["codigo"], h["fecha"])
            if clave in vistos:
                continue
            vistos.add(clave)
            unicos.append(h)

        return {"hechos": unicos[:12], "agenda": agenda}
    except Exception:
        return vacio


# ── Dividendos (ex-dividendo y pago) ──────────────────────────────────────

def _dividendos_tradingview(ticker):
    """Fechas FUTURAS de ex-dividendo y pago vía TradingView.
    Comprobado: cubre NYSE (KO, MCD), donde Nasdaq devuelve vacío. NUNCA lanza."""
    try:
        from tradingview_screener import Query, col
        variantes = [str(ticker).upper()]
        if "-" in variantes[0]:
            variantes.append(variantes[0].replace("-", "."))
        for tk in variantes:
            _, df = (Query()
                     .select("name", "dividend_ex_date_upcoming",
                             "dividend_payment_date_upcoming")
                     .where(col("name") == tk)
                     .limit(1)
                     .get_scanner_data())
            if df is None or df.empty:
                continue
            fila = df.iloc[0]

            def _fecha(clave):
                v = fila.get(clave)
                try:
                    ts = float(v)
                except (TypeError, ValueError):
                    return None
                if not ts or ts != ts or ts <= 0:      # 0, None o NaN
                    return None
                return datetime.fromtimestamp(int(ts)).date()

            return {"ex": _fecha("dividend_ex_date_upcoming"),
                    "pago": _fecha("dividend_payment_date_upcoming")}
        return {}
    except Exception:
        return {}


def _dividendos_nasdaq(ticker):
    """Ex-dividendo y pago vía Nasdaq. Cubre los listados en NASDAQ (AAPL);
    para NYSE devuelve vacío, por eso solo se usa como respaldo. NUNCA lanza."""
    try:
        for tk in {str(ticker).upper(), str(ticker).upper().replace("-", ".")}:
            datos = _nasdaq_json(f"/api/quote/{tk}/dividends?assetclass=stocks")
            if not datos:
                continue
            ex   = _parse_fecha_us(datos.get("exDividendDate"))
            pago = _parse_fecha_us(datos.get("dividendPaymentDate"))
            filas = ((datos.get("dividends") or {}).get("rows") or [])
            historico = [_parse_fecha_us(f.get("exOrEffDate")) for f in filas]
            historico = [f for f in historico if f]
            if ex or historico:
                return {"ex": ex, "pago": pago, "historico": historico}
        return {}
    except Exception:
        return {}


def _cadencia_dias(historico):
    """Días entre pagos según el histórico (91 ≈ trimestral). None si no hay."""
    try:
        fechas = sorted(set(historico), reverse=True)[:5]
        if len(fechas) < 2:
            return None
        huecos = [(fechas[i] - fechas[i + 1]).days for i in range(len(fechas) - 1)]
        huecos = [h for h in huecos if 20 < h < 400]
        if not huecos:
            return None
        huecos.sort()
        return huecos[len(huecos) // 2]        # mediana
    except Exception:
        return None


def _eventos_dividendo(ticker):
    """Agenda de dividendos, encadenando TradingView → Nasdaq → proyección."""
    eventos = []
    try:
        tv = _dividendos_tradingview(ticker)
        nas = _dividendos_nasdaq(ticker) if not tv.get("ex") else {}

        ex   = tv.get("ex")   or nas.get("ex")
        pago = tv.get("pago") or nas.get("pago")
        estimada = False

        # Si la fecha conocida ya pasó, se proyecta la siguiente con la cadencia
        # observada (marcándola como estimada, nunca como confirmada).
        if ex and ex < _hoy():
            cadencia = _cadencia_dias(nas.get("historico") or [])
            if cadencia:
                proyectada = ex
                while proyectada < _hoy():
                    proyectada += timedelta(days=cadencia)
                pago, ex, estimada = None, proyectada, True
            else:
                ex = None

        ev = _evento(ex, "Fecha ex-dividendo", TIPO_DIVIDENDO,
                     "Último día para comprar la acción y tener derecho al próximo dividendo.",
                     "TradingView/Nasdaq", estimada=estimada)
        if ev:
            eventos.append(ev)
        ev = _evento(pago, "Pago de dividendo", TIPO_DIVIDENDO,
                     "Fecha en la que el dividendo se abona a los accionistas.",
                     "TradingView/Nasdaq")
        if ev:
            eventos.append(ev)
    except Exception:
        pass
    return eventos


# ── Agregador ─────────────────────────────────────────────────────────────

def _eventos_earnings(earnings):
    """Convierte el próximo reporte (ya obtenido por get_earnings_data) en un
    evento de agenda. No hace red: reutiliza lo que ya está en memoria."""
    try:
        fecha = _parse_iso((earnings or {}).get("next_earnings"))
        return [e for e in [_evento(
            fecha, "Reporte de resultados", TIPO_EARNINGS,
            "Publicación de resultados trimestrales: el evento de mayor volatilidad del calendario.",
            "Earnings")] if e]
    except Exception:
        return []


def get_catalyst_events(ticker, info=None, earnings=None):
    """Agenda de eventos futuros + hechos relevantes recientes de un ticker.

    Devuelve SIEMPRE un dict con la misma forma:
        {"agenda": [...], "hechos_recientes": [...], "fuentes": [...]}

    Cada evento de `agenda`: {fecha, dias, titulo, tipo, desc, fuente, estimada}.
    NUNCA lanza y NUNCA se queda sin agenda mientras la capa estática funcione.
    """
    resultado = {"agenda": [], "hechos_recientes": [], "fuentes": []}
    try:
        tk = str(ticker or "").upper().strip()
        if not tk:
            return resultado

        cacheado = _load_cache(f"events_{tk}", ttl_hours=TTL_EVENTS)
        if cacheado and isinstance(cacheado, dict) and cacheado.get("agenda"):
            return cacheado

        info = info or {}
        agenda = []
        hechos = []
        fuentes = []

        # ── CAPA 0: sin red, nunca falla ──
        try:
            estaticos = proximos_eventos_estaticos(
                tk, info.get("sector"), info.get("industry"),
                horizonte_dias=HORIZONTE_DIAS)
            if estaticos:
                agenda += estaticos
                fuentes.append("calendario")
        except Exception:
            pass

        agenda += _eventos_earnings(earnings)

        # ── CAPA 1: red, en PARALELO (el coste es el timeout más lento) ──
        tareas = {
            "SEC":        lambda: _sec_hechos_relevantes(tk),
            "dividendos": lambda: _eventos_dividendo(tk),
        }
        try:
            with ThreadPoolExecutor(max_workers=len(tareas)) as executor:
                futuros = {executor.submit(fn): nombre for nombre, fn in tareas.items()}
                for futuro in as_completed(futuros, timeout=_TIMEOUT * 2 + 4):
                    nombre = futuros[futuro]
                    try:
                        datos = futuro.result(timeout=1)
                    except Exception:
                        continue
                    if nombre == "SEC":
                        if datos.get("hechos"):
                            hechos += datos["hechos"]
                            fuentes.append("SEC")
                        agenda += datos.get("agenda") or []
                    elif datos:
                        agenda += datos
                        fuentes.append("dividendos")
        except Exception:
            # Ni siquiera un fallo del pool puede tumbar la agenda estática
            pass

        # Deduplicar por (título, fecha) y ordenar cronológicamente
        vistos, limpia = set(), []
        for ev in sorted(agenda, key=lambda e: e.get("fecha", "9999")):
            clave = (ev.get("titulo"), ev.get("fecha"))
            if clave in vistos or not ev.get("fecha"):
                continue
            vistos.add(clave)
            limpia.append(ev)

        resultado = {"agenda": limpia, "hechos_recientes": hechos, "fuentes": fuentes}

        # No cachear un resultado inútil: un fallo transitorio no debe congelar
        # "sin eventos" durante todo el TTL.
        if limpia:
            _save_cache(f"events_{tk}", resultado)
        return resultado
    except Exception:
        return resultado

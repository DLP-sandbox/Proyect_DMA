"""
Calendario de eventos corporativos — CAPA 0: 100% determinista, SIN red, SIN IA.

POR QUÉ EXISTE
--------------
La sección de Catalizadores solo conocía los earnings. Los eventos que de verdad
mueven una acción muchas veces son OTROS: el WWDC de Apple, el GTC de NVIDIA, el
I/O de Google, el re:Invent de Amazon, la conferencia de salud de J.P. Morgan…
Para esos eventos NO existe una API pública gratuita y fiable.

La única forma de tenerlos SIEMPRE (también cuando la red falla o Yahoo bloquea
la IP del servidor) es un calendario estático con REGLAS DE RECURRENCIA: cada
evento se declara por el mes y la semana en que se celebra habitualmente, y aquí
se resuelve a la próxima fecha real contando desde hoy.

GARANTÍA
--------
Este módulo NO hace peticiones de red, NO llama a la IA y NUNCA lanza. En el peor
caso devuelve una lista vacía. Es el suelo sobre el que se apoyan las fuentes de
red (`data/events.py`): aunque TODAS fallen, la agenda sigue teniendo contenido.

FECHAS ESTIMADAS
----------------
Una fecha resuelta por recurrencia es una ESTIMACIÓN, no un anuncio oficial. Por
eso todo evento de aquí sale con `estimada=True`, para que la UI lo marque como
aproximado y el modelo no lo presente como confirmado. Nunca se inventa una
precisión que no tenemos.
"""
from datetime import date, timedelta

from data.industry_labels import _norm, _es_vacio


# ── Tipos de evento (vocabulario cerrado que consume la UI) ────────────────
# Se mantienen en español y en minúsculas. La UI los usa para el color y el
# icono textual; añadir uno nuevo NO rompe nada (cae al estilo por defecto).
TIPO_PRODUCTO   = "producto"      # keynote, lanzamiento, conferencia de desarrolladores
TIPO_CONFERENCIA = "conferencia"  # feria sectorial, congreso
TIPO_OPERATIVO  = "operativo"     # entregas, ventas de temporada
TIPO_ACCIONISTA = "accionista"    # junta anual, día del inversor
TIPO_MACRO      = "macro"         # Fed, rebalanceo de índices
TIPO_EARNINGS   = "earnings"      # reporte de resultados
TIPO_DIVIDENDO  = "dividendo"     # ex-dividendo / pago
TIPO_REGULATORIO = "regulatorio"  # aprobaciones, resoluciones


def _ev(nombre, mes, semana=None, dia=None, tipo=TIPO_PRODUCTO, desc="", dow=0):
    """Declara una regla de recurrencia anual.

    `mes`     1-12.
    `semana`  1-4 → primera/segunda/tercera/cuarta semana de ese mes. Cae en el
              día `dow` de esa semana (0 = lunes por defecto, porque los eventos
              de industria casi siempre arrancan en lunes o martes; el
              rebalanceo de índices usa `dow=4`, viernes).
    `dia`     día fijo del mes, cuando la fecha es estable (ej: entregas de Tesla
              los primeros días del trimestre).
    Se usa `semana` O `dia`, no ambos.
    """
    return {"nombre": nombre, "mes": mes, "semana": semana, "dia": dia,
            "tipo": tipo, "desc": desc, "dow": dow}


# ── Eventos emblemáticos por empresa ──────────────────────────────────────
# Curado a mano. Solo eventos ANUALES y RECURRENTES cuya ventana es estable año
# tras año; los eventos de una sola vez no van aquí (los detecta la capa de
# noticias/SEC). Si una empresa no está, no pasa nada: recibe igualmente los
# eventos de su sector y los de mercado.
_EVENTOS_EMPRESA = {
    # ── Tecnología / plataformas ──
    "AAPL":  [_ev("WWDC — conferencia de desarrolladores", 6, semana=1, desc="Apple presenta el software del año (iOS, macOS) y a veces hardware nuevo."),
              _ev("Keynote de otoño (iPhone)", 9, semana=2, desc="Presentación del nuevo iPhone: el evento comercial más importante del año.")],
    "MSFT":  [_ev("Microsoft Build", 5, semana=3, desc="Conferencia de desarrolladores: anuncios de Azure, IA y Copilot."),
              _ev("Microsoft Ignite", 11, semana=3, desc="Evento para empresas y TI: novedades de nube y productividad.")],
    "GOOGL": [_ev("Google I/O", 5, semana=2, desc="Conferencia de desarrolladores: Android, IA y servicios."),
              _ev("Evento de hardware Pixel", 10, semana=1, desc="Presentación de la gama Pixel y dispositivos.")],
    "GOOG":  [_ev("Google I/O", 5, semana=2, desc="Conferencia de desarrolladores: Android, IA y servicios."),
              _ev("Evento de hardware Pixel", 10, semana=1, desc="Presentación de la gama Pixel y dispositivos.")],
    "AMZN":  [_ev("AWS re:Invent", 12, semana=1, desc="El gran evento de la nube de Amazon: anuncios de AWS e IA."),
              _ev("Prime Day", 7, semana=2, tipo=TIPO_OPERATIVO, desc="Evento de ventas propio: referencia del consumo online.")],
    "META":  [_ev("Meta Connect", 9, semana=4, desc="Realidad mixta, gafas inteligentes e IA generativa.")],
    "NVDA":  [_ev("GTC — GPU Technology Conference", 3, semana=3, desc="Keynote de Jensen Huang: hoja de ruta de chips de IA."),
              _ev("Computex (Taipéi)", 5, semana=4, tipo=TIPO_CONFERENCIA, desc="Feria clave del hardware asiático.")],
    "AMD":   [_ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Presentación de nuevas gamas de CPU/GPU."),
              _ev("Computex (Taipéi)", 5, semana=4, tipo=TIPO_CONFERENCIA, desc="Feria clave del hardware asiático.")],
    "INTC":  [_ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Anuncios de nuevas generaciones de procesadores."),
              _ev("Intel Innovation", 9, semana=3, desc="Evento técnico: hoja de ruta de fabricación y producto.")],
    "QCOM":  [_ev("Snapdragon Summit", 10, semana=4, desc="Presentación del chip insignia para móviles del año."),
              _ev("MWC Barcelona", 3, semana=1, tipo=TIPO_CONFERENCIA, desc="Congreso mundial del móvil.")],
    "AVGO":  [_ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Escaparate del ecosistema de conectividad.")],
    "TSM":   [_ev("Simposio Tecnológico de TSMC", 4, semana=4, desc="Hoja de ruta de nodos de fabricación (3nm, 2nm)."),
              _ev("SEMICON Taiwán", 9, semana=2, tipo=TIPO_CONFERENCIA, desc="Feria de la industria de semiconductores.")],
    "ASML":  [_ev("Día del Inversor", 11, semana=2, tipo=TIPO_ACCIONISTA, desc="Actualización de la demanda de litografía y objetivos a largo plazo.")],
    "MU":    [_ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Anuncios de memoria de alto ancho de banda para IA.")],
    "ARM":   [_ev("Arm Tech Symposia", 10, semana=3, desc="Hoja de ruta de arquitecturas y licencias.")],
    "ORCL":  [_ev("Oracle CloudWorld", 9, semana=2, desc="Anuncios de nube, bases de datos e IA.")],
    "CRM":   [_ev("Dreamforce", 9, semana=3, desc="El mayor evento de software empresarial: producto y clientes.")],
    "ADBE":  [_ev("Adobe MAX", 10, semana=2, desc="Novedades de creatividad e IA generativa."),
              _ev("Adobe Summit", 3, semana=3, desc="Evento de marketing digital y analítica.")],
    "NOW":   [_ev("ServiceNow Knowledge", 5, semana=1, desc="Conferencia anual de producto y clientes.")],
    "SNOW":  [_ev("Snowflake Summit", 6, semana=1, desc="Conferencia de datos e IA: anuncios de plataforma.")],
    "PLTR":  [_ev("AIPCon", 3, semana=1, desc="Evento de clientes de la plataforma de IA.")],
    "IBM":   [_ev("IBM Think", 5, semana=2, desc="Conferencia de nube híbrida, IA y computación cuántica.")],
    "CSCO":  [_ev("Cisco Live", 6, semana=2, desc="Conferencia de redes y seguridad.")],
    "DELL":  [_ev("Dell Technologies World", 5, semana=3, desc="Anuncios de infraestructura de IA y almacenamiento.")],
    "HPQ":   [_ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Renovación de gamas de PC e impresión.")],
    "PANW":  [_ev("Ignite (Palo Alto Networks)", 11, semana=2, desc="Conferencia de ciberseguridad y producto.")],
    "CRWD":  [_ev("Fal.Con", 9, semana=3, desc="Conferencia anual de ciberseguridad de CrowdStrike.")],
    "ZS":    [_ev("Zenith Live", 6, semana=1, desc="Conferencia de seguridad en la nube.")],
    "SHOP":  [_ev("Shopify Editions", 6, semana=4, desc="Tanda semestral de novedades de producto."),
              _ev("Black Friday / Cyber Monday", 11, semana=4, tipo=TIPO_OPERATIVO, desc="Pico de volumen de comercio: la empresa publica cifras récord.")],

    # ── Consumo y automoción ──
    "TSLA":  [_ev("Entregas trimestrales", 1, dia=2, tipo=TIPO_OPERATIVO, desc="Cifra de producción y entregas del trimestre: mueve la acción con fuerza."),
              _ev("Entregas trimestrales", 4, dia=2, tipo=TIPO_OPERATIVO, desc="Cifra de producción y entregas del trimestre."),
              _ev("Entregas trimestrales", 7, dia=2, tipo=TIPO_OPERATIVO, desc="Cifra de producción y entregas del trimestre."),
              _ev("Entregas trimestrales", 10, dia=2, tipo=TIPO_OPERATIVO, desc="Cifra de producción y entregas del trimestre."),
              _ev("Junta anual de accionistas", 6, semana=2, tipo=TIPO_ACCIONISTA, desc="Actualización de hoja de ruta (robotaxi, energía, IA).")],
    "RIVN":  [_ev("Entregas trimestrales", 1, dia=3, tipo=TIPO_OPERATIVO, desc="Producción y entregas del trimestre."),
              _ev("Entregas trimestrales", 4, dia=3, tipo=TIPO_OPERATIVO, desc="Producción y entregas del trimestre."),
              _ev("Entregas trimestrales", 7, dia=3, tipo=TIPO_OPERATIVO, desc="Producción y entregas del trimestre."),
              _ev("Entregas trimestrales", 10, dia=3, tipo=TIPO_OPERATIVO, desc="Producción y entregas del trimestre.")],
    "F":     [_ev("Ventas mensuales / Detroit Auto Show", 1, semana=2, tipo=TIPO_OPERATIVO, desc="Presentaciones de modelo y cifras de ventas.")],
    "GM":    [_ev("Día del Inversor", 10, semana=2, tipo=TIPO_ACCIONISTA, desc="Objetivos de eléctricos y márgenes.")],
    "NKE":   [_ev("Día del Inversor", 11, semana=2, tipo=TIPO_ACCIONISTA, desc="Objetivos de marca, canal directo y márgenes.")],
    "SBUX":  [_ev("Día del Inversor", 9, semana=3, tipo=TIPO_ACCIONISTA, desc="Plan de aperturas y crecimiento en China.")],
    "MCD":   [_ev("Día del Inversor", 12, semana=1, tipo=TIPO_ACCIONISTA, desc="Estrategia de aperturas, digital y márgenes.")],
    "DIS":   [_ev("D23 / Presentación de contenidos", 8, semana=2, desc="Calendario de estrenos de cine y streaming."),
              _ev("Upfronts de publicidad", 5, semana=3, tipo=TIPO_OPERATIVO, desc="Venta anticipada de publicidad televisiva.")],
    "NFLX":  [_ev("Upfronts de publicidad", 5, semana=3, tipo=TIPO_OPERATIVO, desc="Venta de inventario publicitario del plan con anuncios.")],
    "COST":  [_ev("Ventas mensuales comparables", 1, dia=8, tipo=TIPO_OPERATIVO, desc="Costco publica ventas cada mes: termómetro del consumo.")],
    "WMT":   [_ev("Temporada navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="Black Friday y campaña de fin de año: el trimestre decisivo."),
              _ev("Reunión anual de accionistas", 6, semana=1, tipo=TIPO_ACCIONISTA, desc="Actualización de estrategia minorista.")],
    "TGT":   [_ev("Temporada navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="Campaña de fin de año: el trimestre decisivo.")],
    "HD":    [_ev("Temporada de primavera (jardín/reforma)", 3, semana=3, tipo=TIPO_OPERATIVO, desc="El trimestre más fuerte del año para la reforma del hogar.")],
    "KO":    [_ev("Día del Inversor", 11, semana=3, tipo=TIPO_ACCIONISTA, desc="Objetivos de crecimiento y cartera de marcas.")],
    "PEP":   [_ev("Día del Inversor", 2, semana=3, tipo=TIPO_ACCIONISTA, desc="Objetivos de bebidas y snacks.")],
    "COKE":  [_ev("Temporada alta de bebidas", 6, semana=1, tipo=TIPO_OPERATIVO, desc="Verano: pico estacional de consumo de bebidas.")],

    # ── Salud y farmacia ──
    "LLY":   [_ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="La cita del año del sector salud: guías y datos clínicos."),
              _ev("Congreso ADA (diabetes)", 6, semana=3, tipo=TIPO_CONFERENCIA, desc="Datos clínicos de fármacos metabólicos y de obesidad.")],
    "NVO":   [_ev("Congreso ADA (diabetes)", 6, semana=3, tipo=TIPO_CONFERENCIA, desc="Datos clínicos de diabetes y obesidad."),
              _ev("Congreso EASD", 9, semana=3, tipo=TIPO_CONFERENCIA, desc="Congreso europeo de diabetes.")],
    "MRK":   [_ev("Congreso ASCO (oncología)", 6, semana=1, tipo=TIPO_CONFERENCIA, desc="Resultados de ensayos oncológicos.")],
    "PFE":   [_ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Guías anuales y cartera de I+D.")],
    "JNJ":   [_ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Guías anuales y cartera de I+D.")],
    "ABBV":  [_ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Guías anuales y cartera de I+D.")],
    "AMGN":  [_ev("Congreso ASCO (oncología)", 6, semana=1, tipo=TIPO_CONFERENCIA, desc="Resultados de ensayos oncológicos.")],
    "ISRG":  [_ev("Congreso SAGES (cirugía)", 3, semana=3, tipo=TIPO_CONFERENCIA, desc="Adopción de cirugía robótica.")],
    "UNH":   [_ev("Día del Inversor", 11, semana=4, tipo=TIPO_ACCIONISTA, desc="Guía de beneficios del año siguiente."),
              _ev("Inscripción abierta de Medicare", 10, semana=2, tipo=TIPO_REGULATORIO, desc="Periodo que define la base de afiliados del año.")],

    # ── Finanzas ──
    "JPM":   [_ev("Día del Inversor", 5, semana=4, tipo=TIPO_ACCIONISTA, desc="Objetivos de rentabilidad y capital."),
              _ev("Resultados de las pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determina la capacidad de dividendos y recompras.")],
    "BAC":   [_ev("Resultados de las pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determina la capacidad de dividendos y recompras.")],
    "WFC":   [_ev("Resultados de las pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determina la capacidad de dividendos y recompras.")],
    "GS":    [_ev("Resultados de las pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determina la capacidad de dividendos y recompras.")],
    "BRK-B": [_ev("Junta anual de Berkshire (Omaha)", 5, semana=1, tipo=TIPO_ACCIONISTA, desc="La reunión anual más seguida del mundo: visión y cartera."),
              _ev("Carta anual a los accionistas", 2, semana=4, tipo=TIPO_ACCIONISTA, desc="Documento de referencia con la lectura del año.")],
    "BRK-A": [_ev("Junta anual de Berkshire (Omaha)", 5, semana=1, tipo=TIPO_ACCIONISTA, desc="La reunión anual más seguida del mundo: visión y cartera."),
              _ev("Carta anual a los accionistas", 2, semana=4, tipo=TIPO_ACCIONISTA, desc="Documento de referencia con la lectura del año.")],
    "V":     [_ev("Día del Inversor", 2, semana=3, tipo=TIPO_ACCIONISTA, desc="Volúmenes de pago y nuevos flujos.")],
    "MA":    [_ev("Día del Inversor", 11, semana=2, tipo=TIPO_ACCIONISTA, desc="Volúmenes de pago y servicios de valor añadido.")],
    "NU":    [_ev("Día del Inversor", 11, semana=1, tipo=TIPO_ACCIONISTA, desc="Crecimiento de clientes en Latinoamérica y rentabilidad.")],
    "COIN":  [_ev("Ciclo de halving de Bitcoin / regulación cripto", 4, semana=3, tipo=TIPO_REGULATORIO, desc="Hitos del mercado cripto que marcan volúmenes de intermediación.")],

    # ── Energía e industria ──
    "XOM":   [_ev("Día del Inversor / plan corporativo", 12, semana=2, tipo=TIPO_ACCIONISTA, desc="Plan de inversión y producción del año siguiente.")],
    "CVX":   [_ev("Día del Inversor", 2, semana=4, tipo=TIPO_ACCIONISTA, desc="Plan de inversión y retribución al accionista.")],
    "BA":    [_ev("Feria aeronáutica (Farnborough / París)", 7, semana=3, tipo=TIPO_CONFERENCIA, desc="Donde se anuncian los grandes pedidos de aviones.")],
    "CAT":   [_ev("Día del Inversor", 5, semana=2, tipo=TIPO_ACCIONISTA, desc="Ciclo de maquinaria e infraestructura.")],
    "GE":    [_ev("Día del Inversor", 3, semana=2, tipo=TIPO_ACCIONISTA, desc="Objetivos de aviación y energía.")],
    "LMT":   [_ev("Presupuesto de defensa de EE. UU.", 3, semana=2, tipo=TIPO_REGULATORIO, desc="La propuesta presupuestaria fija la demanda del sector.")],
    "RTX":   [_ev("Presupuesto de defensa de EE. UU.", 3, semana=2, tipo=TIPO_REGULATORIO, desc="La propuesta presupuestaria fija la demanda del sector.")],
    "VRT":   [_ev("Día del Inversor", 11, semana=3, tipo=TIPO_ACCIONISTA, desc="Demanda de infraestructura para centros de datos de IA.")],
}


# ── Eventos genéricos por SECTOR ──────────────────────────────────────────
# Se aplican a CUALQUIER empresa de ese sector, de modo que ningún ticker se
# quede sin agenda. Las claves cubren los DOS vocabularios (yfinance y
# TradingView), igual que hace `industry_labels`.
_EVENTOS_SECTOR = {
    # Tecnología
    "technology": [
        _ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="La mayor feria de electrónica: marca el tono del año en tecnología."),
        _ev("MWC Barcelona", 3, semana=1, tipo=TIPO_CONFERENCIA, desc="Congreso mundial del móvil y la conectividad."),
    ],
    "electronic technology": [
        _ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="La mayor feria de electrónica del año."),
        _ev("SEMICON West", 7, semana=2, tipo=TIPO_CONFERENCIA, desc="Feria de la cadena de suministro de semiconductores."),
    ],
    "technology services": [
        _ev("CES (Las Vegas)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Feria de referencia del sector tecnológico."),
    ],
    "communication services": [
        _ev("MWC Barcelona", 3, semana=1, tipo=TIPO_CONFERENCIA, desc="Congreso mundial del móvil y la conectividad."),
    ],
    "communications": [
        _ev("MWC Barcelona", 3, semana=1, tipo=TIPO_CONFERENCIA, desc="Congreso mundial del móvil y la conectividad."),
    ],
    # Salud
    "healthcare": [
        _ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="La cita del año del sector salud: guías anuales y acuerdos."),
        _ev("Congreso ASCO (oncología)", 6, semana=1, tipo=TIPO_CONFERENCIA, desc="Presentación de resultados de ensayos clínicos."),
    ],
    "health technology": [
        _ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="La cita del año del sector salud: guías anuales y acuerdos."),
        _ev("Congreso ASCO (oncología)", 6, semana=1, tipo=TIPO_CONFERENCIA, desc="Presentación de resultados de ensayos clínicos."),
    ],
    "health services": [
        _ev("Conferencia J.P. Morgan Healthcare", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Guías anuales del sector salud."),
    ],
    # Consumo
    "consumer cyclical": [
        _ev("Black Friday y campaña navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="El periodo que decide el año en consumo discrecional."),
    ],
    "consumer discretionary": [
        _ev("Black Friday y campaña navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="El periodo que decide el año en consumo discrecional."),
    ],
    "retail trade": [
        _ev("Black Friday y campaña navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="El periodo que decide el año en el comercio minorista."),
        _ev("NRF Big Show (retail)", 1, semana=2, tipo=TIPO_CONFERENCIA, desc="Feria del comercio minorista: tendencias y tecnología."),
    ],
    "consumer services": [
        _ev("Temporada alta de viajes de verano", 6, semana=3, tipo=TIPO_OPERATIVO, desc="Pico estacional de demanda en ocio y viajes."),
    ],
    "consumer defensive": [
        _ev("Campaña navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="Pico estacional de consumo básico."),
    ],
    "consumer non-durables": [
        _ev("Campaña navideña", 11, semana=4, tipo=TIPO_OPERATIVO, desc="Pico estacional de consumo."),
    ],
    # Energía
    "energy": [
        _ev("Reunión de la OPEP+", 6, semana=1, tipo=TIPO_REGULATORIO, desc="Decisión de cuotas de producción: mueve el precio del crudo."),
        _ev("Reunión de la OPEP+", 12, semana=1, tipo=TIPO_REGULATORIO, desc="Decisión de cuotas de producción para el año siguiente."),
    ],
    "energy minerals": [
        _ev("Reunión de la OPEP+", 6, semana=1, tipo=TIPO_REGULATORIO, desc="Decisión de cuotas de producción: mueve el precio del crudo."),
    ],
    # Finanzas
    "financial services": [
        _ev("Pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determinan cuánto capital puede devolverse al accionista."),
    ],
    "finance": [
        _ev("Pruebas de estrés de la Fed", 6, semana=4, tipo=TIPO_REGULATORIO, desc="Determinan cuánto capital puede devolverse al accionista."),
    ],
    # Industria
    "industrials": [
        _ev("Feria industrial de Hannover", 4, semana=2, tipo=TIPO_CONFERENCIA, desc="Referencia de automatización y bienes de equipo."),
    ],
    "producer manufacturing": [
        _ev("Feria industrial de Hannover", 4, semana=2, tipo=TIPO_CONFERENCIA, desc="Referencia de automatización y bienes de equipo."),
    ],
}


# ── Eventos de MERCADO (aplican a todas las acciones) ──────────────────────
_DESC_REBALANCEO = ("El tercer viernes del trimestre se reajustan los índices: "
                    "pico de volumen y posibles entradas o salidas de la acción.")
_EVENTOS_MERCADO = [
    _ev("Rebalanceo trimestral de índices", m, semana=3, dow=4,
        tipo=TIPO_MACRO, desc=_DESC_REBALANCEO)
    for m in (3, 6, 9, 12)
]


# ── Resolución de fechas ──────────────────────────────────────────────────

def _dia_de_semana_del_mes(anio, mes, semana, dow=0):
    """Día `dow` (0=lunes … 4=viernes) de la semana `semana` (1-4) de ese mes.
    None si algo no cuadra."""
    try:
        d = date(anio, mes, 1)
        # Primera ocurrencia de ese día de la semana en el mes
        d += timedelta(days=(int(dow) - d.weekday()) % 7)
        d += timedelta(weeks=max(0, int(semana) - 1))
        # Si se pasó de mes (mes corto + semana 4/5), retroceder una semana
        while d.month != mes:
            d -= timedelta(days=7)
        return d
    except (ValueError, TypeError):
        return None


def _fecha_fija(anio, mes, dia):
    try:
        return date(anio, mes, int(dia))
    except (ValueError, TypeError):
        return None


def _proxima_fecha(regla, hoy):
    """Resuelve una regla a la próxima ocurrencia >= hoy. None si no se puede."""
    for anio in (hoy.year, hoy.year + 1):
        if regla.get("semana"):
            f = _dia_de_semana_del_mes(anio, regla["mes"], regla["semana"],
                                       regla.get("dow", 0))
        else:
            f = _fecha_fija(anio, regla["mes"], regla.get("dia") or 1)
        if f and f >= hoy:
            return f
    return None


def proximos_eventos_estaticos(ticker, sector=None, industry=None,
                               horizonte_dias=270):
    """Agenda determinista (sin red) para un ticker.

    Devuelve una lista de dicts ordenada por fecha:
        {fecha 'YYYY-MM-DD', dias, titulo, tipo, desc, fuente, estimada}

    NUNCA lanza: ante cualquier problema devuelve [].
    """
    try:
        hoy = date.today()
        limite = hoy + timedelta(days=int(horizonte_dias))
        tk = str(ticker or "").upper().strip()

        reglas = []
        reglas += _EVENTOS_EMPRESA.get(tk, [])
        # Variante con punto/guion (BRK.B ↔ BRK-B) por si la fuente cambió de estilo
        if not _EVENTOS_EMPRESA.get(tk):
            alt = tk.replace(".", "-") if "." in tk else tk.replace("-", ".")
            reglas += _EVENTOS_EMPRESA.get(alt, [])

        for etiqueta in (sector, industry):
            if not _es_vacio(etiqueta):
                reglas += _EVENTOS_SECTOR.get(_norm(etiqueta), [])

        reglas += _EVENTOS_MERCADO

        candidatos = []
        for r in reglas:
            f = _proxima_fecha(r, hoy)
            if not f or f > limite:
                continue
            candidatos.append((f, r))

        # Ordenar ANTES de deduplicar: un evento declarado varias veces (las
        # cuatro entregas trimestrales de Tesla, el rebalanceo de los 4 meses)
        # debe quedarse con la ocurrencia MÁS PRÓXIMA, no con la primera que
        # aparezca en el diccionario.
        candidatos.sort(key=lambda x: x[0])

        eventos = []
        vistos = set()
        for f, r in candidatos:
            if r["nombre"] in vistos:
                continue
            vistos.add(r["nombre"])
            eventos.append({
                "fecha":    f.isoformat(),
                "dias":     (f - hoy).days,
                "titulo":   r["nombre"],
                "tipo":     r.get("tipo", TIPO_PRODUCTO),
                "desc":     r.get("desc", ""),
                "fuente":   "calendario",
                "estimada": True,   # resuelto por recurrencia, no es fecha oficial
            })

        return eventos
    except Exception:
        return []

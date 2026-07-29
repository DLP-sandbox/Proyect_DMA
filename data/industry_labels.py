"""
Etiquetas de sector e industria en ESPAÑOL (100% deterministas, sin IA).

POR QUÉ EXISTE
--------------
El panel "Información" del Overview necesita decir, en una frase corta, a qué se
dedica la empresa. La descripción larga de yfinance (`longBusinessSummary`) no
sirve para eso: viene en INGLÉS y en la nube (Render, con Yahoo bloqueado) llega
vacía. En cambio `sector` e `industry` SIEMPRE están disponibles, porque
`get_company_info` ya tiene respaldo de TradingView.

Aquí se traducen esos dos campos con mapas estáticos. Coste: 0 créditos de IA,
0 llamadas de red, resultado idéntico en local y en Render.

DOS VOCABULARIOS
----------------
`get_company_info` devuelve el vocabulario de yfinance cuando responde y el de
TradingView cuando cae al respaldo, y NO son iguales:

    yfinance     "Internet Content & Information"  ·  "Consumer Defensive"
    TradingView  "Internet Software/Services"      ·  "Consumer Non-Durables"

Por eso los mapas incluyen AMBOS. Las claves se normalizan (minúsculas, espacios
colapsados) para que no importen mayúsculas ni dobles espacios.

GARANTÍA
--------
`describe_business()` y `sector_es()` NUNCA lanzan y NUNCA devuelven vacío: si
una etiqueta no está mapeada se devuelve tal cual vino (en inglés, pero legible)
antes que dejar el hueco en blanco.
"""


# Valores que las fuentes devuelven como "no lo sé" y que NO deben mostrarse
# como si fueran un dato real (yfinance rellena "Unknown" cuando no tiene sector).
_VACIOS = {"", "unknown", "n/a", "n/d", "none", "-", "—", "nan"}


def _norm(s) -> str:
    """Clave de búsqueda: minúsculas y espacios colapsados."""
    if not s:
        return ""
    return " ".join(str(s).split()).strip().lower()


def _es_vacio(s) -> bool:
    return _norm(s) in _VACIOS


# ── Sectores ────────────────────────────────────────────────────────────────
# Los 19 de TradingView + los 11 de yfinance (recogidos en vivo del escáner).
_SECTOR_ES = {
    # TradingView
    "commercial services":      "Servicios comerciales",
    "communications":           "Comunicaciones",
    "consumer durables":        "Consumo duradero",
    "consumer non-durables":    "Consumo no duradero",
    "consumer services":        "Servicios al consumidor",
    "distribution services":    "Distribución",
    "electronic technology":    "Tecnología electrónica",
    "energy minerals":          "Energía",
    "finance":                  "Finanzas",
    "health services":          "Servicios de salud",
    "health technology":        "Tecnología sanitaria",
    "industrial services":      "Servicios industriales",
    "non-energy minerals":      "Minería y materiales",
    "process industries":       "Industria de procesos",
    "producer manufacturing":   "Manufactura industrial",
    "retail trade":             "Comercio minorista",
    "technology services":      "Servicios tecnológicos",
    "transportation":           "Transporte",
    "utilities":                "Servicios públicos",
    "miscellaneous":            "Diversificado",
    # yfinance
    "technology":               "Tecnología",
    "communication services":   "Servicios de comunicación",
    "consumer cyclical":        "Consumo cíclico",
    "consumer defensive":       "Consumo defensivo",
    "financial services":       "Servicios financieros",
    "healthcare":               "Salud",
    "industrials":              "Industria",
    "energy":                   "Energía",
    "basic materials":          "Materiales básicos",
    "real estate":              "Inmobiliario",
}


# ── Industrias → frase corta de "a qué se dedica" ───────────────────────────
# Las 108 de TradingView + las más frecuentes de yfinance.
_INDUSTRY_ES = {
    # ── TradingView ──
    "advertising/marketing services":    "Publicidad y marketing",
    "aerospace & defense":               "Aeroespacial y defensa",
    "agricultural commodities/milling":  "Materias primas agrícolas",
    "air freight/couriers":              "Transporte aéreo de carga y paquetería",
    "airlines":                          "Aerolíneas",
    "alternative power generation":      "Generación de energía renovable",
    "aluminum":                          "Aluminio",
    "apparel/footwear":                  "Ropa y calzado",
    "apparel/footwear retail":           "Tiendas de ropa y calzado",
    "auto parts: oem":                   "Componentes para fabricantes de autos",
    "automotive aftermarket":            "Repuestos y accesorios de automoción",
    "beverages: alcoholic":              "Bebidas alcohólicas",
    "beverages: non-alcoholic":          "Bebidas no alcohólicas",
    "biotechnology":                     "Biotecnología",
    "broadcasting":                      "Radio y televisión",
    "building products":                 "Materiales y productos de construcción",
    "cable/satellite tv":                "Televisión por cable y satélite",
    "casinos/gaming":                    "Casinos y juego",
    "catalog/specialty distribution":    "Distribución especializada",
    "chemicals: agricultural":           "Química agrícola y fertilizantes",
    "chemicals: major diversified":      "Química diversificada",
    "chemicals: specialty":              "Química especializada",
    "coal":                              "Carbón",
    "computer communications":           "Equipos de red y comunicaciones",
    "computer peripherals":              "Periféricos informáticos",
    "computer processing hardware":      "Hardware y ordenadores",
    "construction materials":            "Materiales de construcción",
    "consumer sundries":                 "Productos de consumo diversos",
    "containers/packaging":              "Envases y embalaje",
    "contract drilling":                 "Perforación petrolera por contrato",
    "data processing services":          "Procesamiento de datos y pagos",
    "department stores":                 "Grandes almacenes",
    "discount stores":                   "Tiendas de descuento",
    "drugstore chains":                  "Cadenas de farmacias",
    "electric utilities":                "Electricidad",
    "electrical products":               "Productos eléctricos",
    "electronic components":             "Componentes electrónicos",
    "electronic equipment/instruments":  "Equipos e instrumentos electrónicos",
    "electronic production equipment":   "Equipos de producción electrónica",
    "electronics/appliances":            "Electrónica y electrodomésticos",
    "electronics distributors":          "Distribución de electrónica",
    "engineering & construction":        "Ingeniería y construcción",
    "environmental services":            "Servicios medioambientales",
    "finance/rental/leasing":            "Financiación y arrendamiento",
    "financial conglomerates":           "Conglomerado financiero",
    "financial publishing/services":     "Información y servicios financieros",
    "food distributors":                 "Distribución de alimentos",
    "food retail":                       "Supermercados",
    "food: major diversified":           "Alimentación diversificada",
    "food: meat/fish/dairy":             "Carne, pescado y lácteos",
    "food: specialty/candy":             "Alimentación especializada y dulces",
    "forest products":                   "Productos forestales",
    "gas distributors":                  "Distribución de gas",
    "home furnishings":                  "Muebles y decoración",
    "home improvement chains":           "Tiendas de bricolaje y hogar",
    "homebuilding":                      "Construcción de viviendas",
    "hospital/nursing management":       "Hospitales y residencias",
    "hotels/resorts/cruise lines":       "Hoteles, resorts y cruceros",
    "household/personal care":           "Cuidado personal y del hogar",
    "industrial conglomerates":          "Conglomerado industrial",
    "industrial machinery":              "Maquinaria industrial",
    "industrial specialties":            "Productos industriales especializados",
    "information technology services":   "Servicios y consultoría informática",
    "insurance brokers/services":        "Correduría de seguros",
    "integrated oil":                    "Petróleo integrado",
    "internet retail":                   "Comercio electrónico",
    "internet software/services":        "Software y servicios de internet",
    "investment banks/brokers":          "Banca de inversión y corretaje",
    "investment managers":               "Gestión de inversiones",
    "investment trusts/mutual funds":    "Fondos de inversión",
    "life/health insurance":             "Seguros de vida y salud",
    "major banks":                       "Banca",
    "major telecommunications":          "Telecomunicaciones",
    "managed health care":               "Seguros médicos y salud gestionada",
    "marine shipping":                   "Transporte marítimo",
    "media conglomerates":               "Conglomerado de medios",
    "medical distributors":              "Distribución de material médico",
    "medical specialties":               "Equipos y tecnología médica",
    "metal fabrication":                 "Transformación de metales",
    "miscellaneous commercial services": "Servicios comerciales diversos",
    "miscellaneous manufacturing":       "Manufactura diversificada",
    "motor vehicles":                    "Fabricación de automóviles",
    "movies/entertainment":              "Cine y entretenimiento",
    "multi-line insurance":              "Seguros multirramo",
    "office equipment/supplies":         "Equipos y material de oficina",
    "oil & gas pipelines":               "Oleoductos y gasoductos",
    "oil & gas production":              "Extracción de petróleo y gas",
    "oil refining/marketing":            "Refino y distribución de petróleo",
    "oilfield services/equipment":       "Servicios y equipos petroleros",
    "other consumer services":           "Servicios al consumidor",
    "other consumer specialties":        "Productos de consumo especializados",
    "other metals/minerals":             "Metales y minerales",
    "other transportation":              "Transporte",
    "packaged software":                 "Software",
    "personnel services":                "Servicios de personal y empleo",
    "pharmaceuticals: generic":          "Medicamentos genéricos",
    "pharmaceuticals: major":            "Farmacéutica",
    "pharmaceuticals: other":            "Farmacéutica especializada",
    "precious metals":                   "Metales preciosos",
    "publishing: books/magazines":       "Edición de libros y revistas",
    "publishing: newspapers":            "Prensa",
    "pulp & paper":                      "Papel y celulosa",
    "property/casualty insurance":       "Seguros de daños",
    "railroads":                         "Ferrocarriles",
    "real estate development":           "Promoción inmobiliaria",
    "real estate investment trusts":     "Inversión inmobiliaria (REIT)",
    "recreational products":             "Productos de ocio y recreo",
    "regional banks":                    "Banca regional",
    "restaurants":                       "Restaurantes",
    "semiconductors":                    "Semiconductores",
    "specialty insurance":               "Seguros especializados",
    "specialty stores":                  "Tiendas especializadas",
    "specialty telecommunications":      "Telecomunicaciones especializadas",
    "steel":                             "Acero",
    "telecommunications equipment":      "Equipos de telecomunicaciones",
    "textiles":                          "Textil",
    "tobacco":                           "Tabaco",
    "tools & hardware":                  "Herramientas y ferretería",
    "trucking":                          "Transporte por carretera",
    "trucks/construction/farm machinery": "Camiones y maquinaria pesada",
    "water utilities":                   "Agua",
    "wholesale distributors":            "Distribución mayorista",
    "wireless telecommunications":       "Telefonía móvil",

    # ── yfinance (nombres distintos para lo mismo) ──
    "internet content & information":    "Contenido y publicidad en internet",
    "software - infrastructure":         "Software de infraestructura",
    "software - application":            "Software de aplicaciones",
    "consumer electronics":              "Electrónica de consumo",
    "semiconductor equipment & materials": "Equipos para semiconductores",
    "information technology services":   "Servicios y consultoría informática",
    "communication equipment":           "Equipos de comunicación",
    "computer hardware":                 "Hardware y ordenadores",
    "electronic components":             "Componentes electrónicos",
    "banks - regional":                  "Banca regional",
    "banks - diversified":               "Banca diversificada",
    "capital markets":                   "Mercados de capitales",
    "credit services":                   "Crédito y tarjetas de pago",
    "asset management":                  "Gestión de activos",
    "insurance - diversified":           "Seguros diversificados",
    "insurance - property & casualty":   "Seguros de daños",
    "insurance - life":                  "Seguros de vida",
    "financial data & stock exchanges":  "Datos financieros y bolsas",
    "drug manufacturers - general":      "Farmacéutica",
    "drug manufacturers - specialty & generic": "Farmacéutica especializada y genéricos",
    "medical devices":                   "Dispositivos médicos",
    "medical instruments & supplies":    "Instrumental y material médico",
    "diagnostics & research":            "Diagnóstico e investigación",
    "healthcare plans":                  "Seguros médicos",
    "medical care facilities":           "Centros médicos y hospitales",
    "beverages - non-alcoholic":         "Bebidas no alcohólicas",
    "beverages - brewers":               "Cerveceras",
    "beverages - wineries & distilleries": "Bodegas y destilerías",
    "packaged foods":                    "Alimentación envasada",
    "confectioners":                     "Dulces y confitería",
    "farm products":                     "Productos agrícolas",
    "household & personal products":     "Cuidado personal y del hogar",
    "discount stores":                   "Tiendas de descuento",
    "grocery stores":                    "Supermercados",
    "internet retail":                   "Comercio electrónico",
    "specialty retail":                  "Tiendas especializadas",
    "apparel retail":                    "Tiendas de ropa",
    "apparel manufacturing":             "Fabricación de ropa",
    "footwear & accessories":            "Calzado y accesorios",
    "luxury goods":                      "Artículos de lujo",
    "home improvement retail":           "Tiendas de bricolaje y hogar",
    "auto manufacturers":                "Fabricación de automóviles",
    "auto parts":                        "Componentes de automoción",
    "auto & truck dealerships":          "Concesionarios de vehículos",
    "travel services":                   "Servicios de viajes",
    "lodging":                           "Hoteles y alojamiento",
    "resorts & casinos":                 "Resorts y casinos",
    "entertainment":                     "Entretenimiento",
    "electronic gaming & multimedia":    "Videojuegos y multimedia",
    "advertising agencies":              "Agencias de publicidad",
    "telecom services":                  "Telecomunicaciones",
    "broadcasting":                      "Radio y televisión",
    "publishing":                        "Edición y prensa",
    "aerospace & defense":               "Aeroespacial y defensa",
    "specialty industrial machinery":    "Maquinaria industrial especializada",
    "farm & heavy construction machinery": "Maquinaria agrícola y de construcción",
    "building products & equipment":     "Materiales y productos de construcción",
    "engineering & construction":        "Ingeniería y construcción",
    "integrated freight & logistics":    "Transporte y logística",
    "railroads":                         "Ferrocarriles",
    "trucking":                          "Transporte por carretera",
    "airlines":                          "Aerolíneas",
    "waste management":                  "Gestión de residuos",
    "staffing & employment services":    "Servicios de empleo",
    "consulting services":               "Consultoría",
    "rental & leasing services":         "Alquiler y arrendamiento",
    "conglomerates":                     "Conglomerado",
    "industrial distribution":           "Distribución industrial",
    "oil & gas integrated":              "Petróleo integrado",
    "oil & gas e&p":                     "Extracción de petróleo y gas",
    "oil & gas midstream":               "Transporte y almacenamiento de hidrocarburos",
    "oil & gas refining & marketing":    "Refino y distribución de petróleo",
    "oil & gas equipment & services":    "Servicios y equipos petroleros",
    "utilities - regulated electric":    "Electricidad regulada",
    "utilities - regulated gas":         "Gas regulado",
    "utilities - renewable":             "Energía renovable",
    "utilities - diversified":           "Servicios públicos diversificados",
    "specialty chemicals":               "Química especializada",
    "chemicals":                         "Química",
    "agricultural inputs":               "Insumos agrícolas",
    "gold":                              "Oro",
    "copper":                            "Cobre",
    "steel":                             "Acero",
    "aluminum":                          "Aluminio",
    "building materials":                "Materiales de construcción",
    "packaging & containers":            "Envases y embalaje",
    "paper & paper products":            "Papel y derivados",
    "lumber & wood production":          "Madera",
    "tobacco":                           "Tabaco",
    "real estate services":              "Servicios inmobiliarios",
    "reit - residential":                "Inversión inmobiliaria residencial (REIT)",
    "reit - retail":                     "Inversión inmobiliaria comercial (REIT)",
    "reit - industrial":                 "Inversión inmobiliaria industrial (REIT)",
    "reit - office":                     "Inversión inmobiliaria de oficinas (REIT)",
    "reit - specialty":                  "Inversión inmobiliaria especializada (REIT)",
    "reit - healthcare facilities":      "Inversión inmobiliaria sanitaria (REIT)",
    "reit - hotel & motel":              "Inversión inmobiliaria hotelera (REIT)",
    "reit - diversified":                "Inversión inmobiliaria diversificada (REIT)",
    "reit - mortgage":                   "Inversión inmobiliaria hipotecaria (REIT)",
    "restaurants":                       "Restaurantes",
    "biotechnology":                     "Biotecnología",
    "security & protection services":    "Seguridad y protección",
    "scientific & technical instruments": "Instrumentos científicos y técnicos",
    "solar":                             "Energía solar",
    "shell companies":                   "Sociedad instrumental",
    "pharmaceutical retailers":          "Cadenas de farmacias",
    "medical distribution":              "Distribución de material médico",
    "health information services":       "Servicios de información sanitaria",
    "insurance brokers":                 "Correduría de seguros",
    "mortgage finance":                  "Financiación hipotecaria",
    "financial conglomerates":           "Conglomerado financiero",
    "furnishings, fixtures & appliances": "Muebles y electrodomésticos",
    "residential construction":          "Construcción residencial",
    "personal services":                 "Servicios personales",
    "education & training services":     "Educación y formación",
    "leisure":                           "Ocio",
    "gambling":                          "Juego y apuestas",
    "recreational vehicles":             "Vehículos recreativos",
    "textile manufacturing":             "Textil",
    "food distribution":                 "Distribución de alimentos",
    "marine shipping":                   "Transporte marítimo",
    "airports & air services":           "Aeropuertos y servicios aéreos",
    "uranium":                           "Uranio",
    "coking coal":                       "Carbón metalúrgico",
    "thermal coal":                      "Carbón térmico",
    "silver":                            "Plata",
    "other precious metals & mining":    "Metales preciosos",
    "other industrial metals & mining":  "Metales industriales",
    "electrical equipment & parts":      "Equipos y componentes eléctricos",
    "pollution & treatment controls":    "Control de la contaminación",
    "business equipment & supplies":     "Equipos y material de oficina",
    "infrastructure operations":         "Explotación de infraestructuras",
    "metal fabrication":                 "Transformación de metales",
    "tools & accessories":               "Herramientas y accesorios",
    "semiconductors":                    "Semiconductores",
}


def sector_es(sector) -> str:
    """Sector en español, o CADENA VACÍA si la fuente no tenía el dato.

    Devolver "" (y no "—" ni "Unknown") es deliberado: quien pinta la fila la
    OMITE cuando esto viene vacío, así el panel nunca muestra un hueco ni un
    placeholder. Nunca lanza."""
    try:
        if _es_vacio(sector):
            return ""
        raw = str(sector).strip()
        return _SECTOR_ES.get(_norm(raw), raw)
    except Exception:
        return ""


def describe_business(industry, sector=None) -> str:
    """Frase corta, en español, de a qué se dedica la empresa.

    Cadena de respaldo: industria mapeada → sector mapeado → industria cruda →
    sector crudo → "". Los placeholders de las fuentes ("Unknown", "N/A"…) se
    tratan como AUSENCIA de dato.

    Devuelve "" cuando no hay nada que decir (acción muy poco conocida, fuentes
    caídas…): la fila entera se omite en vez de mostrar "—" o un error.
    Nunca lanza — cualquier excepción también acaba en "" y la fila desaparece."""
    try:
        ind_ok = not _es_vacio(industry)
        sec_ok = not _es_vacio(sector)
        if ind_ok:
            hit = _INDUSTRY_ES.get(_norm(industry))
            if hit:
                return hit
        if sec_ok:
            sec_hit = _SECTOR_ES.get(_norm(sector))
            if sec_hit:
                return sec_hit
        # Sin mapeo: mejor la etiqueta original (legible) que un hueco vacío.
        if ind_ok:
            return str(industry).strip()
        if sec_ok:
            return str(sector).strip()
        return ""
    except Exception:
        return ""

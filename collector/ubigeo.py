"""Mapa estático ubigeoNivel01 -> nombre de departamento.

Los códigos ubigeoNivel01 que devuelve la API de ONPE son `<n>*10000`. OJO:
ONPE NO usa la numeración INEI — ordena los departamentos alfabéticamente y
mueve Callao al puesto 24. Este mapa se verificó contra el propio endpoint
/ubigeos/dep-prov-distritos de ONPE (2026-06-08), no contra INEI.
Los códigos 91xxxx-95xxxx son el voto en el exterior, agrupado por continente.
"""
from __future__ import annotations

DEPARTAMENTOS: dict[int, str] = {
    10000: "Amazonas",
    20000: "Áncash",
    30000: "Apurímac",
    40000: "Arequipa",
    50000: "Ayacucho",
    60000: "Cajamarca",
    70000: "Cusco",
    80000: "Huancavelica",
    90000: "Huánuco",
    100000: "Ica",
    110000: "Junín",
    120000: "La Libertad",
    130000: "Lambayeque",
    140000: "Lima",
    150000: "Loreto",
    160000: "Madre de Dios",
    170000: "Moquegua",
    180000: "Pasco",
    190000: "Piura",
    200000: "Puno",
    210000: "San Martín",
    220000: "Tacna",
    230000: "Tumbes",
    240000: "Callao",
    250000: "Ucayali",
}

EXTERIOR: dict[int, str] = {
    910000: "Exterior – África",
    920000: "Exterior – América",
    930000: "Exterior – Asia",
    940000: "Exterior – Europa",
    950000: "Exterior – Oceanía",
}

NOMBRE_A_UBIGEO = {v: k for k, v in DEPARTAMENTOS.items()}

# Países del exterior: ubigeoNivel02 -> (ISO3, nombre legible). ISO3 hace match
# directo con el GeoJSON mundial (id = ISO_A3), sin fuzzy-matching de nombres.
EXTERIOR_PAISES: dict[int, tuple[str, str]] = {
    910100: ("DZA", "Argelia"),
    910300: ("EGY", "Egipto"),
    910400: ("KEN", "Kenia"),
    910500: ("MAR", "Marruecos"),
    910600: ("ZAF", "Sudáfrica"),
    911200: ("GHA", "Ghana"),
    920100: ("", "Antillas Holandesas"),
    920200: ("ARG", "Argentina"),
    920400: ("BOL", "Bolivia"),
    920500: ("BRA", "Brasil"),
    920600: ("CAN", "Canadá"),
    920700: ("COL", "Colombia"),
    920800: ("CRI", "Costa Rica"),
    920900: ("CUB", "Cuba"),
    921000: ("CHL", "Chile"),
    921100: ("ECU", "Ecuador"),
    921200: ("SLV", "El Salvador"),
    921300: ("USA", "Estados Unidos"),
    921500: ("GTM", "Guatemala"),
    921700: ("HND", "Honduras"),
    921900: ("MEX", "México"),
    922000: ("NIC", "Nicaragua"),
    922100: ("PAN", "Panamá"),
    922200: ("PRY", "Paraguay"),
    922300: ("PRI", "Puerto Rico"),
    922400: ("DOM", "República Dominicana"),
    922600: ("TTO", "Trinidad y Tobago"),
    922700: ("URY", "Uruguay"),
    922800: ("VEN", "Venezuela"),
    923000: ("GUF", "Guayana Francesa"),
    930100: ("KOR", "Corea del Sur"),
    930200: ("CHN", "China"),
    930400: ("IND", "India"),
    930600: ("ISR", "Israel"),
    930700: ("JPN", "Japón"),
    930800: ("LBN", "Líbano"),
    931000: ("THA", "Tailandia"),
    931100: ("IDN", "Indonesia"),
    931300: ("JOR", "Jordania"),
    931500: ("TUR", "Turquía"),
    931900: ("SAU", "Arabia Saudita"),
    932000: ("VNM", "Vietnam"),
    932400: ("IRN", "Irán"),
    932500: ("SGP", "Singapur"),
    932800: ("KWT", "Kuwait"),
    933000: ("MYS", "Malasia"),
    933200: ("PHL", "Filipinas"),
    933700: ("ARE", "Emiratos Árabes Unidos"),
    933800: ("QAT", "Catar"),
    940200: ("DEU", "Alemania"),
    940300: ("AUT", "Austria"),
    940400: ("BEL", "Bélgica"),
    940600: ("CZE", "República Checa"),
    940800: ("DNK", "Dinamarca"),
    940900: ("ESP", "España"),
    941000: ("FIN", "Finlandia"),
    941100: ("FRA", "Francia"),
    941200: ("GBR", "Gran Bretaña"),
    941300: ("GRC", "Grecia"),
    941400: ("NLD", "Holanda"),
    941500: ("HUN", "Hungría"),
    941700: ("ITA", "Italia"),
    941800: ("IRL", "Irlanda"),
    942000: ("LUX", "Luxemburgo"),
    942100: ("MLT", "Malta"),
    942300: ("NOR", "Noruega"),
    942400: ("POL", "Polonia"),
    942500: ("PRT", "Portugal"),
    942600: ("ROU", "Rumanía"),
    942700: ("SWE", "Suecia"),
    942800: ("CHE", "Suiza"),
    942900: ("RUS", "Rusia"),
    943600: ("BLR", "Bielorrusia"),
    943700: ("MKD", "Macedonia"),
    944200: ("AND", "Andorra"),
    950100: ("AUS", "Australia"),
    950200: ("NZL", "Nueva Zelanda"),
}


def nombre_departamento(ubigeo_nivel01: int) -> str:
    """Nombre legible para un ubigeoNivel01; '' si no se reconoce."""
    if ubigeo_nivel01 in DEPARTAMENTOS:
        return DEPARTAMENTOS[ubigeo_nivel01]
    if ubigeo_nivel01 in EXTERIOR:
        return EXTERIOR[ubigeo_nivel01]
    return ""


def es_exterior(ubigeo_nivel01: int) -> bool:
    return ubigeo_nivel01 >= 900000

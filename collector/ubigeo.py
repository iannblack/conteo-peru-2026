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

# Código ISO-ish de 2 letras por departamento, para hacer match con el GeoJSON
# del mapa (usamos el nombre como clave principal; este es respaldo).
NOMBRE_A_UBIGEO = {v: k for k, v in DEPARTAMENTOS.items()}


def nombre_departamento(ubigeo_nivel01: int) -> str:
    """Nombre legible para un ubigeoNivel01; '' si no se reconoce."""
    if ubigeo_nivel01 in DEPARTAMENTOS:
        return DEPARTAMENTOS[ubigeo_nivel01]
    if ubigeo_nivel01 in EXTERIOR:
        return EXTERIOR[ubigeo_nivel01]
    return ""


def es_exterior(ubigeo_nivel01: int) -> bool:
    return ubigeo_nivel01 >= 900000

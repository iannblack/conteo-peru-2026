"""Tests del scraper con un cliente falso (sin red)."""
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scraper import construir_snapshot, _split_votos, _agregar_actas  # noqa: E402
from onpe_client import OnpeError  # noqa: E402


def _part(keiko, sanchez):
    return [
        {"codigoAgrupacionPolitica": 8, "totalVotosValidos": keiko},
        {"codigoAgrupacionPolitica": 10, "totalVotosValidos": sanchez},
    ]


def test_split_votos_ok():
    assert _split_votos(_part(100, 200)) == {"keiko": 100, "sanchez": 200}


def test_split_votos_incompleto_da_none():
    assert _split_votos([{"codigoAgrupacionPolitica": 8, "totalVotosValidos": 100}]) is None


def test_agregar_actas_por_departamento():
    # dos provincias del mismo depto (10000) -> se suman; total se infiere del pct
    mc = [
        {"ubigeoNivel01": 10000, "actasContabilizadas": 90, "porcentajeActasContabilizadas": 90.0},
        {"ubigeoNivel01": 10000, "actasContabilizadas": 50, "porcentajeActasContabilizadas": 100.0},
    ]
    agg = _agregar_actas(mc)
    assert agg[10000]["contabilizadas"] == 140
    assert agg[10000]["total"] == 150  # 100/0.9 + 50/1.0 = 111.1 + 50


class FakeClient:
    """Implementa la interfaz de OnpeClient con data sintética."""

    def __init__(self, deps):
        self.deps = deps  # {ubigeo: {"votos": (k,s), "contab": n, "total": n}}

    def id_eleccion(self):
        return 10

    def totales_nacional(self, eid):
        k = sum(d["votos"][0] for d in self.deps.values())
        s = sum(d["votos"][1] for d in self.deps.values())
        return {
            "actasContabilizadas": 95.0, "contabilizadas": 100, "totalActas": 105,
            "totalVotosEmitidos": k + s + 10, "totalVotosValidos": k + s,
            "participacionCiudadana": 70.0,
        }

    def participantes_nacional(self, eid):
        k = sum(d["votos"][0] for d in self.deps.values())
        s = sum(d["votos"][1] for d in self.deps.values())
        return _part(k, s)

    def mapa_calor_departamentos(self, eid):
        rows = []
        for ub, d in self.deps.items():
            pct = 100 * d["contab"] / d["total"]
            rows.append({"ubigeoNivel01": ub, "actasContabilizadas": d["contab"],
                         "porcentajeActasContabilizadas": pct})
        return rows

    def participantes_departamento(self, eid, ub):
        d = self.deps.get(ub)
        if not d or (d["votos"][0] + d["votos"][1]) == 0:
            return None
        return _part(*d["votos"])

    def totales_ambito(self, eid, ambito):
        return None

    def participantes_ambito(self, eid, ambito):
        return None

    def totales_continente_exterior(self, eid, code):
        return None  # sin exterior en los fixtures base


def _deps_25():
    # 25 departamentos mínimos para pasar el sanity check (>=25)
    return {(i + 1) * 10000: {"votos": (1000, 1000), "contab": 90, "total": 100} for i in range(25)}


def test_construir_snapshot_normaliza_bien():
    snap = construir_snapshot(FakeClient(_deps_25()))
    assert snap["id_eleccion"] == 10
    assert len(snap["regiones"]) == 25
    assert snap["nacional"]["votos"]["keiko"] == 25000
    r0 = snap["regiones"][0]
    assert set(r0) >= {"ubigeo", "nombre", "actas_contabilizadas", "actas_total", "votos"}


def test_pocos_departamentos_lanza_error():
    pocos = {10000: {"votos": (1000, 1000), "contab": 90, "total": 100}}
    with pytest.raises(OnpeError):
        construir_snapshot(FakeClient(pocos))


class FakeClientExt(FakeClient):
    """Cliente con exterior por continente (totalActas real por continente)."""

    EXT = {
        910000: {"total": 6, "contab": 1, "votos": (0, 0)},
        920000: {"total": 1570, "contab": 141, "votos": (11159, 8336)},  # América, pro-Keiko
        930000: {"total": 107, "contab": 2, "votos": (0, 0)},
        940000: {"total": 839, "contab": 17, "votos": (664, 540)},       # Europa
        950000: {"total": 21, "contab": 0, "votos": (0, 0)},
    }

    def totales_continente_exterior(self, eid, code):
        e = self.EXT.get(code)
        return {"totalActas": e["total"], "contabilizadas": e["contab"]} if e else None

    def participantes_departamento(self, eid, ub):
        if ub in self.EXT:
            v = self.EXT[ub]["votos"]
            return _part(*v) if (v[0] + v[1]) else None
        return super().participantes_departamento(eid, ub)


def test_exterior_por_continente_con_total_real():
    snap = construir_snapshot(FakeClientExt(_deps_25()))
    ext = {r["nombre"]: r for r in snap["regiones"] if r["exterior"]}
    assert len(ext) == 5  # 5 continentes
    am = ext["Exterior – América"]
    assert am["actas_total"] == 1570         # total REAL del continente
    assert am["actas_contabilizadas"] == 141
    assert am["votos"]["keiko"] == 11159
    # los 5 totales suman el total exterior conocido (2543)
    assert sum(r["actas_total"] for r in ext.values()) == 2543

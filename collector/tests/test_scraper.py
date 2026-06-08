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

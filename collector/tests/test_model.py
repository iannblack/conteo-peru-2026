"""Tests del modelo con fixtures sintéticos (sin red)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from model import proyectar  # noqa: E402


def _region(ubigeo, nombre, keiko, sanchez, actas_contab, actas_total):
    return {
        "ubigeo": ubigeo,
        "nombre": nombre,
        "exterior": ubigeo >= 900000,
        "actas_contabilizadas": actas_contab,
        "actas_total": actas_total,
        "pct_actas": round(100 * actas_contab / actas_total, 2) if actas_total else 0.0,
        "votos": {"keiko": keiko, "sanchez": sanchez},
    }


def _snap(regiones):
    return {"timestamp_utc": "2026-06-08T00:00:00Z", "regiones": regiones}


def test_estructura_de_salida():
    snap = _snap([_region(10000, "A", 7500, 7500, 100, 100)])
    out = proyectar(snap, n_samples=2000)
    assert set(out) >= {"prob_victoria", "proyeccion_2via_pct", "ganador_proyectado", "por_region"}
    assert abs(out["prob_victoria"]["keiko"] + out["prob_victoria"]["sanchez"] - 1.0) < 1e-9
    assert len(out["por_region"]) == 1


def test_100pct_contado_proyeccion_igual_a_real():
    # votos/acta uniforme (150) y todo contado -> remaining 0 -> banda ~0
    regiones = [
        _region(10000, "A", 9000, 6000, 100, 100),   # Keiko 60%
        _region(20000, "B", 6000, 9000, 100, 100),   # Sánchez 60%
    ]
    out = proyectar(_snap(regiones), n_samples=5000)
    # nacional 2-vías = 15000/30000 = 50% exacto
    assert abs(out["share_actual_2via"]["keiko"] - 50.0) < 1e-6
    band = out["proyeccion_2via_pct"]["keiko"]
    assert abs(band["media"] - 50.0) < 0.05
    assert band["hi"] - band["lo"] < 0.2  # sin nada que falte, banda colapsa
    assert out["frac_faltante"] == 0.0


def test_sesgo_geografico_corrige_hacia_lo_no_contado():
    # Región grande pro-Keiko ya contada; región pro-Sánchez a medio contar.
    # La proyección debe quedar MÁS pro-Sánchez que el conteo actual.
    regiones = [
        _region(10000, "Keikolandia", 80000, 20000, 1000, 1000),   # 80% Keiko, 100% contado
        _region(20000, "Sanchezlandia", 20000, 80000, 500, 1000),  # 20% Keiko, 50% contado
    ]
    out = proyectar(_snap(regiones), n_samples=8000)
    actual = out["share_actual_2via"]["keiko"]
    proyectado = out["proyeccion_2via_pct"]["keiko"]["media"]
    assert proyectado < actual - 1.0  # la corrección mueve la aguja hacia Sánchez
    assert out["frac_faltante"] > 0.1


def test_empate_da_probabilidad_cercana_a_50():
    regiones = [
        _region(10000, "A", 7500, 7500, 90, 100),
        _region(20000, "B", 7500, 7500, 90, 100),
    ]
    out = proyectar(_snap(regiones), n_samples=20000)
    assert 0.30 < out["prob_victoria"]["keiko"] < 0.70


def test_region_sin_contar_no_rompe():
    regiones = [
        _region(10000, "A", 9000, 6000, 100, 100),
        _region(20000, "SinData", 0, 0, 0, 50),  # 0 actas contadas
    ]
    out = proyectar(_snap(regiones), n_samples=2000)
    assert out["prob_victoria"]["keiko"] >= 0.0  # no NaN, no crash

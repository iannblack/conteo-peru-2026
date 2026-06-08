"""Modelo de proyección bayesiano auto-calibrado por geografía.

Idea central (carrera de 2 candidatos, ganador = más votos válidos):

  • Cada departamento tiene una posterior sobre el *share* de Keiko entre los
    votos válidos de los dos candidatos, vía Beta-Binomial:
        p_i ~ Beta(α0 + a_i,  β0 + b_i)
    donde (a_i, b_i) son votos contabilizados de Keiko/Sánchez en el depto i.

  • El prior (α0, β0) es un *pooling parcial* débil centrado en la media
    nacional actual. Departamentos con pocas actas se "encogen" hacia lo
    nacional; los que ya contaron mucho mandan sus propios datos.

  • Lo que falta por contar en cada depto se estima por su *tamaño total*
    (actas totales × votos por acta), NO por lo ya contado — así una región con
    0% contado igual recibe su peso real y el sesgo geográfico se corrige solo.

  • Monte Carlo sobre los p_i → distribución predictiva nacional → probabilidad
    de victoria + intervalo de credibilidad.

Sólo depende de numpy. Sin red, sin I/O: función pura, fácil de testear.
"""
from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_SAMPLES = 20000
DEFAULT_SEED = 12345
DEFAULT_KAPPA = 4.0  # fuerza del prior de pooling (en "pseudo-votos"); débil a propósito
# Error sistemático nacional (en share, 0.06 = 6 puntos) que tendríamos si NADA
# estuviera contado. Se escala por la fracción que falta: temprano en el conteo
# domina la incertidumbre; cerca del 100% se desvanece. Cubre el riesgo de que
# las actas tardías/impugnadas rompan distinto a las ya contadas — algo que el
# muestreo por conglomerados por sí solo no captura.
DEFAULT_SIGMA_FULL = 0.06


def _band(x: np.ndarray) -> dict[str, float]:
    lo, med, hi = np.percentile(x, [2.5, 50, 97.5])
    return {
        "media": round(float(np.mean(x)), 3),
        "lo": round(float(lo), 3),
        "mediana": round(float(med), 3),
        "hi": round(float(hi), 3),
    }


def proyectar(
    snapshot: dict[str, Any],
    n_samples: int = DEFAULT_SAMPLES,
    seed: int = DEFAULT_SEED,
    kappa: float = DEFAULT_KAPPA,
    sigma_full: float = DEFAULT_SIGMA_FULL,
) -> dict[str, Any]:
    regiones = snapshot["regiones"]
    a = np.array([r["votos"]["keiko"] for r in regiones], dtype=float)
    b = np.array([r["votos"]["sanchez"] for r in regiones], dtype=float)
    counted_actas = np.array([r["actas_contabilizadas"] for r in regiones], dtype=float)
    total_actas = np.array([r["actas_total"] for r in regiones], dtype=float)

    n = a + b  # votos válidos de 2 vías contabilizados por depto
    D = len(regiones)

    # Votos por acta estimados POR REGIÓN (de su propio conteo), no por un promedio
    # nacional: usar el promedio nacional inventa "faltantes" fantasma en regiones
    # ya contadas cuya densidad difiere. Las regiones con ~0 actas usan el nacional.
    total_counted_actas = counted_actas.sum()
    vpa_nac = n.sum() / total_counted_actas if total_counted_actas > 0 else 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        vpa_region = np.where(counted_actas > 0, n / np.maximum(counted_actas, 1.0), vpa_nac)
    esperado_total = total_actas * vpa_region
    remaining = np.clip(esperado_total - n, 0.0, None)

    # prior de pooling parcial centrado en la media nacional de 2 vías
    tot_a, tot_b = a.sum(), b.sum()
    p_nac = tot_a / (tot_a + tot_b) if (tot_a + tot_b) > 0 else 0.5
    alpha0 = kappa * p_nac
    beta0 = kappa * (1.0 - p_nac)

    # Bloque "no atribuido": actas en provincias a 0% contado son invisibles para
    # mapa-calor (total = contab/pct → 0/0). Reconciliamos contra el total nacional
    # de actas (que sí conocemos) y modelamos ese resto como una región sintética
    # con share = media nacional pero MÁXIMA incertidumbre (0 actas efectivas → prior
    # ancho). Es un known-unknown: no fingimos saber hacia dónde se inclina.
    nac = snapshot.get("nacional") or {}
    nac_total_actas = float(nac.get("actas_total") or 0)
    exp_nacional = nac_total_actas * vpa_nac
    no_atribuido = max(0.0, exp_nacional - float(esperado_total.sum()))
    if no_atribuido > 0:
        a = np.append(a, 0.0)
        b = np.append(b, 0.0)
        n = np.append(n, 0.0)
        counted_actas = np.append(counted_actas, 0.0)
        remaining = np.append(remaining, no_atribuido)

    p_hat = np.where(n > 0, a / np.maximum(n, 1.0), 0.5)  # share actual de Keiko

    # Tamaño de muestra efectivo = nº de ACTAS contabilizadas, no de votos.
    # Cada acta es un conglomerado (~200 votantes con un share local correlacionado);
    # contar votos como i.i.d. colapsa la incertidumbre a niveles irreales. Usar
    # actas como n_eff es la corrección de muestreo por conglomerados y produce
    # una banda de credibilidad honesta para lo que aún falta contar.
    n_eff = counted_actas
    a_eff = p_hat * n_eff
    b_eff = (1.0 - p_hat) * n_eff

    rng = np.random.default_rng(seed)
    # p[s, i] = share de Keiko muestreado para la región i en la simulación s
    p = rng.beta(alpha0 + a_eff, beta0 + b_eff, size=(n_samples, len(a)))

    keiko_final = a + p * remaining           # (S, D)
    sanchez_final = b + (1.0 - p) * remaining
    keiko_tot = keiko_final.sum(axis=1)        # (S,)
    sanchez_tot = sanchez_final.sum(axis=1)
    denom = keiko_tot + sanchez_tot
    share_keiko = np.where(denom > 0, keiko_tot / denom, 0.5)

    # error sistemático nacional, escalado por la fracción que falta por contar
    _base = exp_nacional if exp_nacional > 0 else esperado_total.sum()
    frac_remaining = float(remaining.sum() / _base) if _base > 0 else 0.0
    sigma_sis = sigma_full * frac_remaining
    if sigma_sis > 0:
        share_keiko = np.clip(share_keiko + rng.normal(0.0, sigma_sis, size=n_samples), 1e-6, 1 - 1e-6)

    win_keiko = (share_keiko > 0.5).mean()

    # resumen por región (determinístico, sobre lo contado)
    por_region = []
    cur_share_keiko = np.where(n > 0, a / np.maximum(n, 1), 0.5)
    proj_share_keiko_region = p.mean(axis=0)  # media posterior del share por depto
    for i, r in enumerate(regiones):
        lider = "keiko" if a[i] >= b[i] else "sanchez"
        share_lider = max(cur_share_keiko[i], 1 - cur_share_keiko[i]) if n[i] > 0 else 0.5
        por_region.append(
            {
                "ubigeo": r["ubigeo"],
                "nombre": r["nombre"],
                "exterior": r["exterior"],
                "pct_actas": r["pct_actas"],
                "lider": lider,
                "margen": round(float(abs(2 * cur_share_keiko[i] - 1) * 100), 2),
                "share_keiko_actual": round(float(cur_share_keiko[i] * 100), 2),
                "share_keiko_proyectado": round(float(proj_share_keiko_region[i] * 100), 2),
                "votos": r["votos"],
            }
        )

    return {
        "metodo": "beta-binomial-pooling-parcial-actas-v1",
        "n_samples": n_samples,
        "kappa": kappa,
        "frac_faltante": round(frac_remaining, 4),
        "sigma_sistematico_pts": round(sigma_sis * 100, 3),
        "ganador_proyectado": "keiko" if win_keiko >= 0.5 else "sanchez",
        "prob_victoria": {
            "keiko": round(float(win_keiko), 4),
            "sanchez": round(float(1 - win_keiko), 4),
        },
        "share_actual_2via": {
            "keiko": round(float(p_nac * 100), 3),
            "sanchez": round(float((1 - p_nac) * 100), 3),
        },
        "proyeccion_2via_pct": {
            "keiko": _band(share_keiko * 100),
            "sanchez": _band((1 - share_keiko) * 100),
        },
        "votos_por_acta_nacional": round(float(vpa_nac), 1),
        "por_region": por_region,
    }

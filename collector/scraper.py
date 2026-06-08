"""Normaliza la data cruda de ONPE a un esquema interno estable.

El resto del pipeline (modelo, frontend) sólo conoce este esquema, no la forma
caprichosa de la API de ONPE. Si ONPE cambia su API, el blast radius queda aquí.

Candidatos canónicos por código de agrupación:
    8  -> "keiko"   (Fuerza Popular)
    10 -> "sanchez" (Juntos por el Perú)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from onpe_client import OnpeClient, OnpeError
from ubigeo import es_exterior, nombre_departamento

COD_KEIKO = 8
COD_SANCHEZ = 10
CANDIDATOS = {
    "keiko": {"nombre": "Keiko Fujimori", "agrupacion": "Fuerza Popular", "codigo": COD_KEIKO},
    "sanchez": {"nombre": "Roberto Sánchez", "agrupacion": "Juntos por el Perú", "codigo": COD_SANCHEZ},
}


def _split_votos(participantes: list[dict[str, Any]]) -> dict[str, int] | None:
    """Extrae {keiko, sanchez} en votos válidos. None si falta algún candidato."""
    out: dict[str, int] = {}
    for row in participantes or []:
        cod = int(row.get("codigoAgrupacionPolitica") or 0)
        votos = int(row.get("totalVotosValidos") or 0)
        if cod == COD_KEIKO:
            out["keiko"] = votos
        elif cod == COD_SANCHEZ:
            out["sanchez"] = votos
    if "keiko" in out and "sanchez" in out:
        return out
    return None


def _agregar_actas(mapa_calor: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """Agrega filas de provincia por ubigeoNivel01 -> {contabilizadas, total}."""
    agg: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])  # [contab, total_estimado]
    for row in mapa_calor:
        dep = int(row.get("ubigeoNivel01") or 0)
        if not dep:
            continue
        contab = float(row.get("actasContabilizadas") or 0)
        pct = float(row.get("porcentajeActasContabilizadas") or 0)
        total = contab / (pct / 100.0) if pct else 0.0
        agg[dep][0] += contab
        agg[dep][1] += total
    return {dep: {"contabilizadas": round(v[0]), "total": round(v[1])} for dep, v in agg.items()}


def construir_snapshot(client: OnpeClient | None = None) -> dict[str, Any]:
    """Baja todo lo necesario y devuelve el snapshot normalizado.

    Lanza OnpeError si la data es insuficiente para confiar en ella (en cuyo caso
    el caller NO debe sobreescribir el último snapshot bueno).
    """
    client = client or OnpeClient()
    eid = client.id_eleccion()

    totales = client.totales_nacional(eid)
    nac_part = client.participantes_nacional(eid)
    nac_votos = _split_votos(nac_part)
    if nac_votos is None:
        raise OnpeError("No se pudo extraer el split nacional Keiko/Sánchez")

    actas_por_dep = _agregar_actas(client.mapa_calor_departamentos(eid))
    if len(actas_por_dep) < 25:
        raise OnpeError(f"mapa-calor devolvió sólo {len(actas_por_dep)} departamentos (<25)")

    regiones: list[dict[str, Any]] = []
    # --- Departamentos del Perú (mapa-calor es confiable a 97% contado) ---
    for dep in sorted(d for d in actas_por_dep if not es_exterior(d)):
        part = client.participantes_departamento(eid, dep)
        votos = _split_votos(part) if part else None
        if votos is None:
            votos = {"keiko": 0, "sanchez": 0}
        actas = actas_por_dep[dep]
        regiones.append(
            {
                "ubigeo": dep,
                "nombre": nombre_departamento(dep) or f"Ubigeo {dep}",
                "exterior": False,
                "actas_contabilizadas": actas["contabilizadas"],
                "actas_total": actas["total"],
                "pct_actas": round(100 * actas["contabilizadas"] / actas["total"], 2)
                if actas["total"]
                else 0.0,
                "votos": votos,
            }
        )

    # --- Exterior como UNA región agregada ---------------------------------
    # No se puede agregar desde mapa-calor: las provincias del exterior a 0% son
    # invisibles (total = contab/pct → 0), así que el total de actas sale absurdo.
    # ONPE sí expone el ámbito exterior (idAmbitoGeografico=2) con su total real,
    # que es lo que el modelo necesita para pesar los ~cientos de miles de votos
    # del extranjero que aún faltan (históricamente pro-Keiko).
    ext_tot = client.totales_ambito(eid, 2)
    ext_part = client.participantes_ambito(eid, 2)
    ext_votos = _split_votos(ext_part) if ext_part else None
    if ext_tot and ext_votos is not None:
        ext_total_actas = int(ext_tot.get("totalActas") or 0)
        ext_contab = int(ext_tot.get("contabilizadas") or 0)
        if ext_total_actas > 0:
            regiones.append(
                {
                    "ubigeo": 900000,
                    "nombre": "Extranjero",
                    "exterior": True,
                    "actas_contabilizadas": ext_contab,
                    "actas_total": ext_total_actas,
                    "pct_actas": round(100 * ext_contab / ext_total_actas, 2),
                    "votos": ext_votos,
                }
            )

    # sanity: la suma regional debe acercarse al nacional
    suma_keiko = sum(r["votos"]["keiko"] for r in regiones)
    suma_sanchez = sum(r["votos"]["sanchez"] for r in regiones)
    if suma_keiko + suma_sanchez == 0:
        raise OnpeError("Suma regional de votos es cero: data no confiable")

    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id_eleccion": eid,
        "fuente": "ONPE — resultadosegundavuelta.onpe.gob.pe",
        "candidatos": CANDIDATOS,
        "nacional": {
            "actas_pct": float(totales.get("actasContabilizadas") or 0),
            "actas_contabilizadas": int(totales.get("contabilizadas") or 0),
            "actas_total": int(totales.get("totalActas") or 0),
            "votos_emitidos": int(totales.get("totalVotosEmitidos") or 0),
            "votos_validos": int(totales.get("totalVotosValidos") or 0),
            "participacion": float(totales.get("participacionCiudadana") or 0),
            "votos": nac_votos,
        },
        "regiones": regiones,
    }

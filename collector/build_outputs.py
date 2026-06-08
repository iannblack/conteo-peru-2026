"""Orquesta scraper + modelo y escribe los JSON que consume el sitio estático.

Salidas (en docs/data/, mismo origen que GitHub Pages → sin CORS):
  • latest.json   — snapshot completo + proyección (lo que pinta el dashboard).
  • history.json  — serie compacta de puntos en el tiempo (gráfico de evolución).

Contrato de error: si ONPE no responde de forma confiable, NO se toca latest.json
(se conserva el último bueno) y el proceso sale con código 1 para que el job de
Actions quede marcado en rojo sin publicar data corrupta.
"""
from __future__ import annotations

import json
import pathlib
import sys

from model import proyectar
from onpe_client import OnpeError
from scraper import construir_snapshot

DATA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "data"
LATEST = DATA / "latest.json"
HISTORY = DATA / "history.json"
MAX_PUNTOS = 3000  # tope de la serie histórica (≈10 días a 5 min)


def _punto_historico(out: dict) -> dict:
    proy = out["proyeccion"]
    return {
        "t": out["timestamp_utc"],
        "actas_pct": out["nacional"]["actas_pct"],
        "prob_keiko": proy["prob_victoria"]["keiko"],
        "keiko": proy["proyeccion_2via_pct"]["keiko"],      # {media, lo, mediana, hi}
        "sanchez": proy["proyeccion_2via_pct"]["sanchez"],
    }


def _append_historia(punto: dict) -> int:
    serie: list[dict] = []
    if HISTORY.exists():
        try:
            serie = json.loads(HISTORY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            serie = []
    if serie and serie[-1].get("t") == punto["t"]:
        serie[-1] = punto  # mismo timestamp: reemplazar (idempotente)
    else:
        serie.append(punto)
    serie = serie[-MAX_PUNTOS:]
    HISTORY.write_text(json.dumps(serie, ensure_ascii=False), encoding="utf-8")
    return len(serie)


def main() -> int:
    try:
        snapshot = construir_snapshot()
    except OnpeError as exc:
        print(f"[ERROR] Data de ONPE no confiable; se conserva latest.json: {exc}", file=sys.stderr)
        return 1

    proyeccion = proyectar(snapshot)
    out = {**snapshot, "proyeccion": proyeccion}

    DATA.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    n_puntos = _append_historia(_punto_historico(out))

    g = proyeccion["ganador_proyectado"]
    pk = proyeccion["prob_victoria"]["keiko"] * 100
    band = proyeccion["proyeccion_2via_pct"][g]
    print(
        f"OK · actas {snapshot['nacional']['actas_pct']}% · "
        f"P(Keiko)={pk:.1f}% · ganador proy.={g} "
        f"({band['lo']}–{band['hi']}%) · serie={n_puntos} puntos"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

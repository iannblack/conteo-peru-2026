# Conteo Perú 2026 — Tracker en vivo + proyección bayesiana

**Fecha:** 2026-06-08
**Estado:** Diseño aprobado
**Contexto:** Segunda vuelta presidencial Perú 2026 (votación 7 jun 2026, conteo en curso). Fuente oficial: `https://resultadosegundavuelta.onpe.gob.pe/main/resumen`.

## Objetivo

Sitio web público en **GitHub Pages** que muestre el conteo oficial de ONPE en (casi) tiempo real y corra una **proyección bayesiana del ganador**, con desglose regional y mapa coroplético. La proyección debe ser estadísticamente defendible y presentada con transparencia metodológica (no es resultado oficial).

## Restricciones que definen la arquitectura

1. **GitHub Pages es estático** — no corre código de servidor.
2. **La API de ONPE rechaza requests normales** — devuelve el HTML del SPA de Angular salvo que se use *fingerprint* de Chrome (`curl_cffi` con `impersonate="chrome124"` o similar). Endpoints internos ya documentados por el repo de referencia.
3. **ONPE casi seguro no envía headers CORS** — un navegador en `*.github.io` no puede llamar la API directo.

Conclusión: el navegador **no** habla con ONPE. Un recolector server-side (GitHub Actions) baja la data y la deja como JSON estático en el repo; el frontend lee ese JSON del mismo origen.

## Referencia externa

Repo público que ya hizo ingeniería inversa de los endpoints de ONPE 2da vuelta 2026: [`oscarzamora/onpe-scraper-2026-2`](https://github.com/oscarzamora/onpe-scraper-2026-2) (auto-discovery, reanudación incremental, salida TSV por mesa). Reusamos su mapeo de endpoints; no su código tal cual.

## Arquitectura

Dos mitades desacopladas dentro del mismo repo:

```
┌─ RECOLECTOR (GitHub Actions, cron ~5 min) ──────────────┐
│  scraper.py        → baja JSON de ONPE (curl_cffi)       │
│  model.py          → modelo bayesiano + Monte Carlo      │
│  build_outputs.py  → orquesta y escribe JSON al repo     │
│  git commit + push                                       │
└──────────────────────────────────────────────────────────┘
                          │ (mismo origen, sin CORS)
┌─ VISOR (GitHub Pages, estático, sin build step) ────────┐
│  /docs/index.html + JS → lee data/*.json y pinta vistas  │
└──────────────────────────────────────────────────────────┘
```

Servir Pages desde `/docs` en `main` (evita una segunda rama). Los JSON viven en `docs/data/` para que Pages los exponga en el mismo origen.

## Componentes

Cada uno con un propósito único, interfaz definida y testeable en aislamiento.

### `scraper.py`
- **Qué hace:** habla con la API de ONPE, normaliza a un esquema interno por departamento.
- **Salida (esquema normalizado):**
  ```
  {
    "timestamp_utc": "2026-06-08T14:05:00Z",
    "nivel": "nacional",
    "actas_procesadas": int, "actas_total": int,
    "candidatos": [{"id": "A", "nombre": "..."}, {"id": "B", "nombre": "..."}],
    "regiones": [
      {
        "ubigeo": "01", "nombre": "Amazonas",
        "electores_habiles": int,
        "actas_procesadas": int, "actas_total": int,
        "votos": {"A": int, "B": int, "blanco": int, "nulo": int}
      }, ...
    ]
  }
  ```
- **Depende de:** `curl_cffi`, endpoints de ONPE.
- **No hace:** modelado ni I/O al repo.

### `model.py`
- **Qué hace:** modelo jerárquico bayesiano (Beta-Binomial con *pooling parcial*) + Monte Carlo.
- **Método:**
  - Por región, posterior sobre el share de cada candidato dado lo contado.
  - Regiones con pocas actas se encogen hacia la media nacional (hyperprior); a más conteo, dominan sus propios datos.
  - Monte Carlo: muestrear share por región → ponderar por `electores_habiles` (padrón) → sumar → distribución predictiva nacional.
  - Salida: probabilidad de victoria por candidato + intervalo de credibilidad (p.ej. 95%).
- **Entrada:** esquema normalizado. **Salida:**
  ```
  {
    "prob_victoria": {"A": 0.87, "B": 0.13},
    "proyeccion": {"A": {"media": 0.512, "lo": 0.498, "hi": 0.526}, "B": {...}},
    "por_region": [{"ubigeo": "01", "lider": "A", "margen": 0.04, "pct_contado": 0.62}, ...],
    "n_samples": int, "metodo": "beta-binomial-pooling-parcial-v1"
  }
  ```
- **Depende de:** solo `numpy`. **Sin red, sin I/O** → testeable con fixtures.
- **Fase 2 (puerta abierta):** anclar las medias regionales con un prior débil de primera vuelta.

### `build_outputs.py`
- **Qué hace:** pega scraper + model, escribe `docs/data/latest.json` y `docs/data/history/<timestamp>.json`.
- **`latest.json`** = `{ ...salida_scraper, "proyeccion": ...salida_model }`.
- **`history/`** acumula snapshots para la vista de evolución (serie histórica gratis vía git).

### Frontend (`docs/`)
- **Stack:** HTML + vanilla JS + Chart.js (gráficos) + SVG/canvas para el mapa. **Sin build step.**
- **Lee:** `data/latest.json` (polling cada ~60 s en el cliente) y `data/history/*.json` (índice en `history/index.json`).
- **Cuatro vistas:**
  1. **Titular** — A vs B (%), % actas procesadas, ganador proyectado + banda, "actualizado hace X min".
  2. **Evolución** — línea temporal de la proyección y su banda de credibilidad (desde `history/`).
  3. **Tabla regional** — por departamento: % contado, líder, margen.
  4. **Mapa coroplético** — Perú por departamento (GeoJSON público de los 25 deptos), coloreado por líder e intensidad de margen.

## Flujo de datos

`ONPE API → scraper (normaliza) → model (bayes + MC) → build_outputs (JSON al repo) → commit → Pages sirve JSON → frontend pinta 4 vistas`.

## Manejo de errores

- Si ONPE no responde o cambia el esquema: el job **falla sin sobreescribir** `latest.json` (queda el último bueno) y loguea el error. El sitio nunca muestra data corrupta.
- El frontend muestra siempre el `timestamp` del dato; si Actions se atrasa, el usuario lo ve.
- Validación de esquema en `scraper.py`: si faltan campos esperados, aborta el job (no escribe).
- **Banner permanente de transparencia:** "Proyección estadística, no resultado oficial" + link a ONPE.

## Testing

- **`model.py`** (fixtures sintéticos, sin red):
  - 100% contado → proyección ≈ resultado real, banda ~0.
  - Sesgo geográfico (regiones de un lado sin contar) → la banda y la media reflejan el faltante.
  - Empate / margen mínimo → `prob_victoria` cercana a 50/50.
- **`scraper.py`**: contra un JSON de respuesta de ONPE guardado como fixture (nunca llama a ONPE en tests). Verifica normalización y validación de esquema.

## Orden de construcción (deploy temprano)

1. `scraper.py` + esquema normalizado — validar contra ONPE real.
2. `model.py` + tests.
3. GitHub Actions cron + commit de JSON.
4. Frontend núcleo: titular + evolución + tabla → **deploy a Pages aquí (ya está vivo)**.
5. Mapa coroplético → fase final.

## Fuera de alcance (YAGNI por ahora)

- Prior histórico de primera vuelta (fase 2 del modelo).
- Conteo por mesa individual (trabajamos a nivel departamento; el padrón regional basta para la ponderación).
- Notificaciones push / alertas.
- Internacionalización más allá de español.

## Decisiones abiertas

- Nombre final del repo (default: `conteo-peru-2026`).
- Frecuencia exacta del cron (arrancar en 5 min; subir si Actions se atrasa).
- Fuente exacta del GeoJSON de departamentos (definir en implementación).

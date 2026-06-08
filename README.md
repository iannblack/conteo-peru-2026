# Conteo Perú 2026 🇵🇪

Tracker en vivo del **conteo oficial de ONPE** (segunda vuelta presidencial 2026) con una
**proyección bayesiana del ganador**, desglose por departamento y mapa coroplético.

> **Proyección estadística, no resultado oficial.** El conteo proviene de ONPE; la proyección
> es un modelo que estima el resultado final y puede equivocarse. Esta página no está afiliada
> a ONPE ni a ninguna agrupación política.

## Cómo funciona

Dos mitades desacopladas, todo dentro de este repo:

```
GitHub Actions (cron ~5 min)                 GitHub Pages (estático)
┌───────────────────────────────┐           ┌──────────────────────────┐
│ collector/build_outputs.py     │  commit   │ docs/  (index.html+app.js)│
│  ├─ onpe_client  (curl_cffi)   │ ───JSON──▶ │  lee docs/data/*.json     │
│  ├─ scraper      (normaliza)   │           │  mismo origen → sin CORS  │
│  └─ model        (bayes + MC)  │           └──────────────────────────┘
└───────────────────────────────┘
```

El navegador **nunca** llama a ONPE (su API rechaza requests sin *fingerprint* de Chrome y no
manda CORS). El recolector corre en Actions, baja la data, calcula la proyección y commitea
`docs/data/latest.json` + `docs/data/history.json`. Pages sirve esos JSON del mismo origen.

## El modelo

`collector/model.py` — Beta-Binomial jerárquico con **pooling parcial** + Monte Carlo:

- Cada departamento tiene una posterior sobre el share de Keiko entre los dos candidatos.
- El **tamaño de muestra efectivo son las actas, no los votos** (cada acta es un conglomerado);
  esto evita la sobre-confianza de tratar millones de votos como independientes.
- Lo que falta se pondera por el **tamaño total** de cada región (auto-calibrado: corrige el
  sesgo geográfico de qué zonas faltan por contar).
- Un **bloque "no atribuido"** modela las actas en provincias a 0% (invisibles en la API) con
  incertidumbre máxima, reconciliando contra el total nacional de actas.
- Un **error sistemático** escalado por la fracción faltante cubre que las actas tardías rompan
  distinto a lo contado.

Salida: probabilidad de victoria + intervalo de credibilidad 95%, nacional y por departamento.

## Desarrollo local

```bash
# correr el recolector una vez (genera docs/data/*.json reales)
cd collector
uv run --with curl_cffi --with numpy python3 build_outputs.py

# tests del modelo y el scraper (sin red)
uv run --with curl_cffi --with numpy --with pytest python3 -m pytest tests/ -q

# previsualizar el sitio
python3 -m http.server 8731 --directory ../docs   # http://localhost:8731
```

## Desplegar en GitHub Pages

1. Crear un repo en GitHub y hacer push de este proyecto.
2. **Settings → Pages →** Source: *Deploy from a branch*, Branch: `main`, Folder: `/docs`.
3. **Settings → Actions → General →** Workflow permissions: *Read and write*.
4. **Actions →** habilitar workflows; correr "Actualizar conteo ONPE" una vez (manual) o esperar al cron.

El sitio queda en `https://<usuario>.github.io/<repo>/`.

## Endpoints de ONPE usados (verificados 2026-06-08)

| Dato | Endpoint | Filtro |
|------|----------|--------|
| idEleccion | `/proceso/proceso-electoral-activo` | — |
| Totales nacional | `/resumen-general/totales` | `tipoFiltro=eleccion` |
| Split A/B nacional | `/resumen-general/participantes` | `tipoFiltro=eleccion` |
| Split A/B por depto | `/resumen-general/participantes` | `ubigeo_nivel_01` + `idUbigeoDepartamento` |
| Actas por provincia | `/resumen-general/mapa-calor` | `tipoFiltro=ubigeo_nivel_01` |

> ONPE puede cambiar su API sin aviso. Si la data deja de actualizarse, revisar `collector/onpe_client.py`.

Mapa GeoJSON: [juaneladio/peru-geojson](https://github.com/juaneladio/peru-geojson).
Diseño completo: [docs/superpowers/specs/](docs/superpowers/specs/2026-06-08-conteo-peru-2026-design.md).

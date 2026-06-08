"""Cliente HTTP para la API interna de ONPE (segunda vuelta 2026).

La API vive detrás del SPA de Angular en resultadosegundavuelta.onpe.gob.pe y
**rechaza requests normales**: salvo que el cliente se haga pasar por Chrome
(curl_cffi `impersonate`), devuelve el HTML del SPA en vez de JSON. Por eso este
módulo es la única pieza que habla con la red.

Endpoints confirmados por ingeniería inversa del bundle de Angular (2026-06-08):
  - /proceso/proceso-electoral-activo           -> idEleccionPrincipal
  - /resumen-general/totales (tipoFiltro=eleccion) -> totales nacionales
  - /resumen-general/participantes              -> split de candidatos
        nacional:    tipoFiltro=eleccion
        por depto:   tipoFiltro=ubigeo_nivel_01 + idUbigeoDepartamento=<n01>
  - /resumen-general/mapa-calor (tipoFiltro=ubigeo_nivel_01) -> actas por provincia

Códigos de agrupación: 8 = Fuerza Popular (Keiko), 10 = Juntos por el Perú (Sánchez).
"""
from __future__ import annotations

import time
from json import JSONDecodeError
from typing import Any

from curl_cffi import requests as curl_requests

BASE_URL = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"
REFERER = "https://resultadosegundavuelta.onpe.gob.pe/main/resumen"


class OnpeError(RuntimeError):
    """La API no respondió como esperamos (HTML del SPA, esquema cambiado, etc.)."""


class OnpeClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 20, max_retries: int = 4):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = curl_requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": REFERER,
                "Accept-Language": "es-PE,es;q=0.9",
            }
        )

    def _get(self, path: str, **params: Any) -> Any:
        """GET con impersonación de Chrome + reintentos. Devuelve payload['data']."""
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = self._session.get(
                    url, params=params or None, impersonate="chrome124", timeout=self.timeout
                )
                if r.status_code == 204 or not r.text.strip():
                    return None  # sin contenido: no es error, simplemente no hay data
                r.raise_for_status()
                try:
                    payload = r.json()
                except JSONDecodeError as exc:
                    snippet = r.text[:160].replace("\n", " ")
                    raise OnpeError(
                        f"Respuesta no-JSON desde {path} (¿bloqueo anti-bot?): {snippet!r}"
                    ) from exc
                if not isinstance(payload, dict) or "data" not in payload:
                    raise OnpeError(f"Payload inesperado desde {path}: {str(payload)[:160]!r}")
                return payload["data"]
            except OnpeError:
                raise  # error de esquema: no tiene sentido reintentar
            except Exception as exc:  # noqa: BLE001 — transitorio de red
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(0.4 * (2**attempt))
        raise OnpeError(f"{path}: {self.max_retries} intentos fallidos") from last_exc

    # ---- endpoints ---------------------------------------------------------

    def id_eleccion(self) -> int:
        data = self._get("/proceso/proceso-electoral-activo")
        if not data or data.get("idEleccionPrincipal") is None:
            raise OnpeError("No se encontró idEleccionPrincipal en proceso activo")
        return int(data["idEleccionPrincipal"])

    def totales_nacional(self, id_eleccion: int) -> dict[str, Any]:
        data = self._get("/resumen-general/totales", idEleccion=id_eleccion, tipoFiltro="eleccion")
        if not isinstance(data, dict):
            raise OnpeError("totales nacional: payload inesperado")
        return data

    def participantes_nacional(self, id_eleccion: int) -> list[dict[str, Any]]:
        data = self._get(
            "/resumen-general/participantes", idEleccion=id_eleccion, tipoFiltro="eleccion"
        )
        if data is None:
            # fallback: el endpoint -nombre también da el split nacional
            data = self._get(
                "/eleccion-presidencial/participantes-ubicacion-geografica-nombre",
                idEleccion=id_eleccion,
                tipoFiltro="eleccion",
            )
        if not isinstance(data, list):
            raise OnpeError("participantes nacional: payload inesperado")
        return data

    def participantes_departamento(self, id_eleccion: int, ubigeo_n01: int) -> list[dict[str, Any]] | None:
        data = self._get(
            "/resumen-general/participantes",
            idEleccion=id_eleccion,
            tipoFiltro="ubigeo_nivel_01",
            idUbigeoDepartamento=ubigeo_n01,
        )
        if data is None:
            return None
        if not isinstance(data, list):
            raise OnpeError(f"participantes depto {ubigeo_n01}: payload inesperado")
        return data

    def mapa_calor_departamentos(self, id_eleccion: int) -> list[dict[str, Any]]:
        """Filas a nivel provincia; el caller las agrega por ubigeoNivel01."""
        data = self._get(
            "/resumen-general/mapa-calor", idEleccion=id_eleccion, tipoFiltro="ubigeo_nivel_01"
        )
        if not isinstance(data, list):
            raise OnpeError("mapa-calor: payload inesperado")
        return data

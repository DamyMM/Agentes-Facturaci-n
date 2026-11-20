"""Lectura de planillas operativas (Google Sheets o .xlsx local). Sólo lectura."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "fuentes.yaml"
MAX_FILAS = 300


def cargar_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


class Fuentes:
    def __init__(self, config: dict | None = None):
        self.config = config if config is not None else cargar_config()

    def permitidas(self, unidad: str | None) -> dict:
        return {k: v for k, v in self.config.items() if unidad is None or unidad in v.get("unidades", [])}

    def hojas(self, nombre: str) -> list[str]:
        f = self.config[nombre]
        if f["tipo"] == "gsheet":
            meta = _sheets_service().spreadsheets().get(spreadsheetId=f["id"], fields="sheets.properties.title").execute()
            return [s["properties"]["title"] for s in meta["sheets"]]
        from openpyxl import load_workbook

        return load_workbook(_ruta(f["path"]), read_only=True).sheetnames

    def leer(self, nombre: str, hoja: str | None, rango: str | None, max_filas: int = MAX_FILAS) -> list[list]:
        f = self.config[nombre]
        if f["tipo"] == "gsheet":
            a1 = f"'{hoja}'!{rango}" if hoja and rango else (f"'{hoja}'" if hoja else rango or "A1:Z300")
            res = _sheets_service().spreadsheets().values().get(spreadsheetId=f["id"], range=a1).execute()
            return res.get("values", [])[:max_filas]
        if f["tipo"] == "xlsx":
            from openpyxl import load_workbook

            wb = load_workbook(_ruta(f["path"]), read_only=True, data_only=True)
            ws = wb[hoja] if hoja else wb.worksheets[0]
            if rango:
                filas = ws.iter_rows(**_rango_a_limites(rango), values_only=True)
            else:
                filas = ws.iter_rows(max_row=max_filas, values_only=True)
            out = []
            for fila in filas:
                out.append(["" if v is None else str(v) for v in fila])
                if len(out) >= max_filas:
                    break
            return out
        raise ValueError(f"tipo de fuente no soportado: {f['tipo']}")

    def buscar(self, nombre: str, hoja: str | None, texto: str) -> dict:
        rango = None if self.config[nombre]["tipo"] == "xlsx" else "A1:ZZ5000"
        filas = self.leer(nombre, hoja, rango, max_filas=5000)
        t = texto.lower()
        # El número de fila es una coordenada de consulta, no un ID permanente (manual, Transporte §3).
        hallazgos = [{"fila": i + 1, "valores": f} for i, f in enumerate(filas) if any(t in str(c).lower() for c in f)]
        return {"encabezado": filas[0] if filas else [], "coincidencias": hallazgos[:50], "total": len(hallazgos)}


def _rango_a_limites(rango: str) -> dict:
    from openpyxl.utils.cell import range_boundaries

    min_col, min_row, max_col, max_row = range_boundaries(rango)
    return {"min_col": min_col, "min_row": min_row, "max_col": max_col, "max_row": max_row}


def _ruta(path: str) -> Path:
    """Rutas relativas se toman desde la raíz del proyecto."""
    p = Path(path)
    return p if p.is_absolute() else RAIZ / p

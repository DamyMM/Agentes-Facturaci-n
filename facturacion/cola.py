"""Cola de pedidos entre las tareas programadas: un archivo JSON por pedido.

Recepción crea un pedido por unidad; el agente de esa unidad lo toma, lo procesa y deja el resultado;
Control lo informa. Cada sesión arranca de cero, así que la carpeta de datos compartidos
(`HG_DATOS_DIR`) es un worktree de la rama `cola` del repo (ver `scripts/cola.sh`).

Estados:
    derivado ─► en_proceso ─► borrador_creado | pendiente | excepcion | duplicado | rechazado
    revision_humana (Recepción no pudo clasificar, o Control lo frenó tras un reintento fallido)
    cualquier estado final ─► informado (lo marca Control al armar el resumen)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from .herramientas import UNIDADES

RAIZ = Path(__file__).resolve().parent.parent

ESTADOS_FINALES = {"borrador_creado", "pendiente", "excepcion", "duplicado", "rechazado"}
ESTADOS = {"derivado", "en_proceso", "revision_humana", "informado"} | ESTADOS_FINALES
TRANSICIONES = {
    "derivado": {"en_proceso", "revision_humana"},
    "en_proceso": ESTADOS_FINALES | {"revision_humana"},
    "revision_humana": {"informado"},
    **{e: {"informado"} for e in ESTADOS_FINALES},
    "informado": set(),
}
AGENTES = {
    "recepcion": "Agente Recepción",
    "despacho": "Agente Despacho",
    "forwarder": "Agente Forwarder",
    "transporte": "Agente Transporte",
    "ecommerce": "Agente Courier",
    "control": "Agente Control",
}


class ErrorCola(Exception):
    pass


def dir_datos(prueba: bool) -> Path:
    """Carpeta de datos compartidos entre tareas. En prueba, por defecto prueba/compartido/."""
    if os.environ.get("HG_DATOS_DIR"):
        return Path(os.environ["HG_DATOS_DIR"])
    return RAIZ / ("prueba/compartido" if prueba else "compartido")


def _ahora() -> dt.datetime:
    return dt.datetime.now().astimezone().replace(microsecond=0)


def _clave(texto: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (texto or "").lower())


class Cola:
    def __init__(self, base: Path):
        self.dir = Path(base) / "pedidos"

    # ------------------------------------------------------------ lectura
    def _ruta(self, pid: str) -> Path:
        if not re.fullmatch(r"HG-\d{8}-\d{4}", pid):
            raise ErrorCola(f"Id de pedido inválido: {pid}")
        return self.dir / f"{pid[3:7]}-{pid[7:9]}" / f"{pid}.json"

    def leer(self, pid: str) -> dict:
        ruta = self._ruta(pid)
        if not ruta.exists():
            raise ErrorCola(f"No existe el pedido {pid}")
        return json.loads(ruta.read_text(encoding="utf-8"))

    def listar(self, estado: str | None = None, unidad: str | None = None) -> list[dict]:
        pedidos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.dir.glob("*/HG-*.json"))]
        return [p for p in pedidos if (estado is None or p["estado"] == estado) and (unidad is None or p["unidad"] == unidad)]

    def _guardar(self, pedido: dict) -> None:
        ruta = self._ruta(pedido["id"])
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(pedido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ escritura
    def crear(self, *, solicitud: str, origen: str, unidad: str | None, cliente: str, referencia: str,
              servicios: str, motivo_unidad: str, agente: str = "recepcion") -> dict:
        """Crea un pedido para UNA unidad. unidad=None → queda en revision_humana."""
        if agente != "recepcion":
            raise ErrorCola("Sólo Recepción crea pedidos.")
        if unidad is not None and unidad not in UNIDADES:
            raise ErrorCola(f"Unidad inválida: {unidad}")
        if unidad and len(_clave(referencia)) < 3:
            raise ErrorCola("Falta la referencia de la operación (carpeta, operación, guía o período).")
        if unidad:
            for p in self.listar(unidad=unidad):
                if (_clave(p["referencia"]) == _clave(referencia) and _clave(p["cliente"]) == _clave(cliente)
                        and _clave(p["servicios"]) == _clave(servicios)
                        and p["estado"] not in {"rechazado", "revision_humana"}):
                    raise ErrorCola(f"Pedido repetido: ya existe {p['id']} ({p['estado']}) para "
                                    f"{unidad} / {cliente} / {referencia}. No se crea otro.")
        ahora = _ahora()
        prefijo = f"HG-{ahora:%Y%m%d}-"
        usados = [int(p.stem[-4:]) for p in self.dir.glob(f"*/{prefijo}*.json")]
        pid = f"{prefijo}{max(usados, default=0) + 1:04d}"
        estado = "derivado" if unidad else "revision_humana"
        pedido = {
            "id": pid,
            "creado": ahora.isoformat(),
            "origen": origen,
            "solicitud": solicitud,
            "unidad": unidad,
            "cliente": cliente,
            "referencia": referencia,
            "servicios": servicios,
            "motivo_unidad": motivo_unidad,
            "estado": estado,
            "resultado": None,
            "historial": [{"hora": ahora.isoformat(), "agente": AGENTES["recepcion"],
                           "accion": f"derivado a {AGENTES[unidad]}" if unidad else "a revisión humana: " + motivo_unidad}],
        }
        self._guardar(pedido)
        return pedido

    def cambiar(self, pid: str, estado: str, agente: str, accion: str, resultado: dict | None = None) -> dict:
        if estado not in ESTADOS:
            raise ErrorCola(f"Estado inválido: {estado}")
        if agente not in AGENTES:
            raise ErrorCola(f"Agente inválido: {agente}")
        p = self.leer(pid)
        if agente in UNIDADES and p["unidad"] != agente:
            raise ErrorCola(f"El pedido {pid} es de {p['unidad']}, no de {agente}.")
        if agente == "recepcion":
            raise ErrorCola("Recepción sólo crea pedidos.")
        if agente == "control" and estado not in {"informado", "revision_humana"}:
            raise ErrorCola("Control sólo informa o manda a revisión humana (para reintentar: reintentar).")
        if agente in UNIDADES and estado == "informado":
            raise ErrorCola("Sólo Control marca los pedidos como informados.")
        if estado not in TRANSICIONES[p["estado"]]:
            raise ErrorCola(f"No se puede pasar de {p['estado']} a {estado} (pedido {pid}).")
        if estado in ESTADOS_FINALES and not resultado:
            raise ErrorCola("Para cerrar un pedido indicá el resultado (qué se creó o qué falta).")
        p["estado"] = estado
        if resultado:
            p["resultado"] = resultado
        p["historial"].append({"hora": _ahora().isoformat(), "agente": AGENTES[agente], "accion": accion})
        self._guardar(p)
        return p

    def tomar(self, pid: str, agente: str) -> dict:
        """El agente de la unidad marca el pedido en_proceso antes de trabajar (evita que lo tomen dos)."""
        return self.cambiar(pid, "en_proceso", agente, "tomado")

    def trabados(self, horas: float = 2.0) -> list[dict]:
        """Pedidos derivados o en proceso sin movimiento hace más de `horas`."""
        limite = _ahora() - dt.timedelta(hours=horas)
        return [p for p in self.listar() if p["estado"] in {"derivado", "en_proceso"}
                and dt.datetime.fromisoformat(p["historial"][-1]["hora"]) < limite]

    def reintentos(self, pid: str) -> int:
        return sum(1 for h in self.leer(pid)["historial"] if h["accion"].startswith("reintento"))

    def reintentar(self, pid: str) -> dict:
        """Control vuelve a derivar un pedido trabado, una sola vez. Después va a revisión humana."""
        p = self.leer(pid)
        if p["estado"] not in {"derivado", "en_proceso"}:
            raise ErrorCola(f"El pedido {pid} está {p['estado']}: no hace falta reintentarlo.")
        if self.reintentos(pid) >= 1:
            raise ErrorCola(f"El pedido {pid} ya se reintentó una vez: mandalo a revisión humana.")
        p["estado"] = "derivado"
        p["historial"].append({"hora": _ahora().isoformat(), "agente": AGENTES["control"],
                               "accion": "reintento por pedido trabado"})
        self._guardar(p)
        return p

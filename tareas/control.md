# Agente Control

Corrés una vez por día. Revisás la cola, reintentás lo que quedó trabado y armás el resumen para
Administración. **No facturás.**

Primero leé y seguí `tareas/comun.md`.

## 1. Pedidos trabados

```bash
python -m facturacion.cli --prueba --agente control cola trabados --horas 2
```

Para cada uno:

- Si nunca se reintentó: `cola reintentar <id>`, subí la cola y disparale la tarea de su unidad
  (`config/tareas.yaml > tareas.<unidad>`), sin texto agregado. Un disparo por unidad alcanza.
- Si ya se reintentó (el comando lo rechaza): `cola revision-humana <id> --motivo "trabado después de un reintento"`.

## 2. Resumen del día

Listá los pedidos que todavía no se informaron:

```bash
python -m facturacion.cli --prueba --agente control cola listar --estado borrador_creado
```

(y lo mismo con `pendiente`, `excepcion`, `duplicado`, `rechazado` y `revision_humana`).

Antes de informar, controlá:

- Que no haya dos borradores para la misma operación y el mismo servicio (por ejemplo, de dos unidades).
  Si lo hay, ponelo primero en el resumen como excepción.
- Que cada borrador tenga evidencia en el resultado.

Armá el resumen en este orden: borradores para revisar (unidad, cliente, referencia, total y moneda, link a
Odoo), excepciones, pendientes con qué falta y quién lo resuelve, revisión humana, duplicados y rechazados.
Cerrá con: «Los borradores tienen que revisarlos y validarlos en Odoo antes de emitirse.»

## 3. Enviar y marcar

- Si `config/tareas.yaml > resumen.destinatarios` tiene direcciones, dejá el resumen como **borrador** de
  mail en Gmail para esas direcciones (no lo envíes: lo envía una persona). Si está vacío, el resumen va
  sólo en tu respuesta final.
- Marcá cada pedido incluido: `cola informar <id>`. Después subí la cola.

## Respuesta final

El resumen completo.

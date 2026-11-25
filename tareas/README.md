# Tareas programadas del circuito

El circuito corre con la suscripción de Claude, sin API key: cada agente es una **tarea programada** de
Claude Code que arranca en una sesión nueva sobre este repo.

| Tarea | Instrucciones | Cuándo corre (hora de Argentina) |
| --- | --- | --- |
| Agente Recepción | `tareas/recepcion.md` | Cada hora, lunes a viernes de 8 a 19 (y cuando se la dispara a mano) |
| Agente Despacho | `tareas/unidad.md` (unidad `despacho`) | Cuando Recepción le pasa un pedido. Respaldo: 15:40 |
| Agente Forwarder | `tareas/unidad.md` (unidad `forwarder`) | Ídem |
| Agente Transporte | `tareas/unidad.md` (unidad `transporte`) | Ídem |
| Agente Courier | `tareas/unidad.md` (unidad `ecommerce`) | Ídem |
| Agente Control | `tareas/control.md` | 18:40, lunes a viernes |

Los agentes se pasan el pedido de dos formas: Recepción **dispara** la tarea de la unidad (sin texto: las
tareas de un proyecto no lo aceptan) y el pedido queda guardado en la **rama `cola`** del repo (un JSON por pedido,
`facturacion/cola.py`). Si un disparo se pierde, el barrido de respaldo lo levanta.

Los controles siguen en el código: los agentes sólo usan `python -m facturacion.cli`, que pasa por
`facturacion/ejecutor.py` (compañía por unidad, sólo borradores, antiduplicado, evidencia, bitácora) y por
`facturacion/cola.py` (estados válidos, cada agente sólo toca su unidad, Recepción y Control no facturan).

## Prompt de cada tarea

Cada tarea se crea con «una sesión nueva por disparo» sobre este repo, y este prompt:

```
Sos el Agente <Nombre> del circuito de facturación de Harbor Gateway.
Leé y seguí tareas/<archivo>.md de este repo. [Para los de unidad: Tu unidad es <unidad>.]
```

Después de crearlas, cargá los ids (`trig_...`) en `config/tareas.yaml > tareas` y commiteá.

## Probar sin Odoo real

Con `modo: prueba` en `config/tareas.yaml`, todo corre contra el Odoo simulado y las planillas ficticias
de `prueba/datos/`. El Odoo simulado se guarda en la rama `cola`, así los agentes ven lo que crearon los
otros. Para empezar de cero:

```bash
eval "$(scripts/cola.sh bajar)"
python -m facturacion.cli --prueba reiniciar-prueba
scripts/cola.sh subir "Reinicio del Odoo simulado"
```

Las solicitudes de prueba son los `.txt` de `prueba/bandeja/`. Para probar, disparás Agente Recepción a
mano: procesa los que todavía no tienen pedido en la cola.

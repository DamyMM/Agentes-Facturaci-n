# Corrida de los 14 casos con el circuito de tareas (24/11/2026)

Corrida a mano, haciendo de cada agente con `python -m facturacion.cli --prueba` y siguiendo
`tareas/*.md`, contra el Odoo simulado y `prueba/datos/`. Sin API key. Todavía no son tareas
programadas reales: esto prueba los comandos, la cola y las instrucciones.

Recepción creó 15 pedidos (el caso 13 se partió por unidad). El pedido de flete del caso 13 lo frenó el
control de repetidos, porque ya existía el del caso 7 para la misma operación y el mismo servicio.

| Caso | Pedido | Agente | Resultado | ¿Coincide con lo esperado? |
| --- | --- | --- | --- | --- |
| 1 | 0001 | Transporte | Borrador ARS 850.000 (retiro y devolución). Demora y desvío pendientes | Sí |
| 2 | 0002 | Transporte | Pendiente: sólo turno; factura del proveedor «1» | Sí |
| 3 | 0003 | Transporte | Rechazado: BA01-26 cancelada | Sí |
| 4 | 0004 | Transporte | Duplicado: ya existe FA-A 00004-00000202. Informa 22436-26 vs 22437-26 | Sí |
| 5 | 0005 | Despacho | Borrador USD 510 (honorarios 450 + gastos 60). Cuenta y orden ARS aparte. Plazo 21/11 10:30, vencido | Sí |
| 6 | 0006 | Despacho | Pendiente: sin liberación | Sí |
| 7 | 0007 | Forwarder | Borrador USD 2.980. Límite 23/11 (vencido). Reemisión del BL no suma | Sí |
| 8 | 0008 | Forwarder | Pendiente: sin tarifa aérea y plazo de exportación no definido | Sí |
| 9 | 0009 | Forwarder | Borrador USD 175 (5 × 35). Transporte no factura | Sí |
| 10 | 0010 | Courier | Pendiente: falta el período | Sí |
| 11 | 0011 | Courier | Borrador ARS 288.000: 22 TLEA, 3 MANI, 1 REENV (sólo C933 tiene REENV) | Sí |
| 12 | 0012 | Courier | Pendiente: la quincena cierra el 30/11; C945 cuenta un solo REENV, C939 no cuenta, C951 afuera | Sí, más prudente: no crea borrador antes del cierre |
| 13 | 0013, 0014 (+ repetido) | Despacho, Transporte | Pendientes: no encontraron la operación. El flete ya estaba en 0007 | Sí |
| 14 | 0015 | Recepción | Revisión humana: falta cliente y operación | Sí |

Control: 0 pedidos trabados; los 15 quedaron `informado`.

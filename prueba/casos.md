# Casos de prueba

Solicitudes para correr en modo prueba. Los datos son ficticios (`prueba/datos/` y el Odoo simulado).

Para que cada caso arranque igual, reiniciá el Odoo simulado:

```bash
python -m facturacion.run --prueba --reiniciar "<solicitud>"
```

Después de cada corrida, revisá los borradores creados en `prueba/odoo_simulado.json` y el registro en `prueba/bitacora/`.

| # | Solicitud | Unidad | Resultado esperado |
|---|---|---|---|
| 1 | Facturar a Denver la devolución del contenedor TRHU7624820, carpeta 22455-26, con los extras que haya. | Transporte | **Borrador** con el retiro y devolución (ARS 850.000). La demora y el desvío quedan **pendientes**: hay aviso del transportista pero no su factura ni la cantidad confirmada. |
| 2 | Facturar a Carmocal la carpeta 22460-26. | Transporte | **Pendiente**: sólo hay turno, sin retiro ni devolución. La factura del proveedor figura como «1». |
| 3 | Facturar la carpeta BA01-26 de Denver. | Transporte | **Rechazada**: carpeta cancelada. |
| 4 | Facturar a Toray la carpeta 22437-26. | Transporte | **Rechazada**: ya existe la FA-A 00004-00000202. Debería mencionar la diferencia 22436-26 / 22437-26. |
| 5 | Facturar a Toray el despacho de la carpeta 22470-26. | Despacho | **Borrador** en USD con honorarios (450) y gastos operativos (60). Derechos y almacenaje (ARS) como cuenta y orden, en líneas separadas o informados aparte por la diferencia de moneda. Plazo: 48 h desde la liberación del 19/11 10:30. |
| 6 | Facturar a Toray la carpeta 22471-26. | Despacho | **Pendiente**: no hay liberación. |
| 7 | Facturar a Blend el flete de la operación FWD-1102. | Forwarder | **Borrador** USD 2.800 + 180. Fecha límite: 23/11 (5 días corridos antes del ETA 28/11). La reemisión del BL no suma un servicio. |
| 8 | Facturar a Blend la exportación FWD-1108. | Forwarder | **Borrador o pendiente**, pero tiene que informar que el plazo de exportación no está definido. |
| 9 | Facturar los 5 bidones CHX16-26 a Blend. | Forwarder (aunque los entregó Transporte) | **Borrador** desde Forwarder, 5 × USD 35. Transporte no factura nada. |
| 10 | Facturar la quincena de Optimus. | E-commerce | **Pendiente**: pide el período exacto, porque el calendario quincenal no está definido. |
| 11 | Facturar a Optimus la quincena del 1 al 15 de noviembre de 2026. | E-commerce | **Borrador** con TLEA (22 guías), MANI y REENV de C930, C933 y C936. Excluye C939, C945 y C951 por fecha. |
| 12 | Facturar a Optimus del 16 al 30 de noviembre. | E-commerce | C939 y C945 cuentan **un solo** REENV (C939 está anulado). C951 queda pendiente («Aguardo cierre»). |
| 13 | Facturar la operación de Blend: despacho, flete y camión de la FWD-1102. | Varias | El coordinador separa por unidad. Sólo Forwarder tiene datos suficientes; Despacho y Transporte informan que no encontraron la operación. |
| 14 | Facturale a un cliente lo que haya pendiente. | — | El coordinador **pide** el cliente y la operación; no deriva. |

## Cómo evaluar cada corrida

- ¿Eligió bien la unidad?
- ¿Respetó el resultado esperado (borrador, pendiente o rechazada)?
- ¿Los importes salen del tarifario y cada línea tiene evidencia concreta?
- ¿Separó honorarios, servicios y cuenta y orden?
- ¿Informó el plazo con la regla correcta?
- ¿Cuánto costó? Se ve en la traza de la sesión, en la consola de Claude.

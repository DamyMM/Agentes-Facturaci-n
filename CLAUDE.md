# Circuito de facturación Harbor Gateway

Sistema de agentes (Claude Managed Agents) que recibe solicitudes de facturación, las deriva a un especialista por unidad de negocio (Despacho, Forwarder, Transporte, E-commerce/Courier) y crea la factura en Odoo **como borrador**. Administración la valida.

## Estructura

- `facturacion/prompts.py`: system prompts. Las reglas salen del *Manual de procesos de Harbor Gateway* (19/11/2026). Si cambiás una regla de negocio, citá de qué parte del manual o de qué decisión sale.
- `facturacion/herramientas.py`: herramientas custom que ven los agentes.
- `facturacion/ejecutor.py`: ejecuta esas herramientas con controles del lado servidor (compañía por unidad, sólo borradores, antiduplicado, evidencia obligatoria, bitácora). Los controles de seguridad van acá, no en los prompts.
- `facturacion/setup_agents.py`: crea o actualiza los agentes. Hay que correrlo después de cambiar prompts o herramientas.
- `facturacion/cli.py` y `facturacion/cola.py`: comandos de terminal y cola de pedidos que usan las tareas programadas (sin API key). Cada agente sólo actúa sobre su unidad; los controles siguen en `ejecutor.py`.
- `tareas/`: instrucciones de las 6 tareas programadas (Recepción, Despacho, Forwarder, Transporte, Courier, Control). `config/tareas.yaml`: modo e ids de las tareas.
- `scripts/cola.sh`: baja y sube la rama `cola`, donde las tareas se pasan los pedidos.
- `facturacion/run.py`: procesa una solicitud con la API de Anthropic (circuito anterior). `--prueba` usa `odoo_simulado.py` y `prueba/datos/`.
- `config/`: empresas y fuentes reales (`*.yaml`) y de prueba (`*.prueba.yaml`).
- `prueba/casos.md`: casos de prueba con el resultado esperado.

## Reglas para trabajar en este repo

- Nunca agregar herramientas que validen, publiquen o envíen facturas, registren cobros o escriban en las planillas, salvo que el usuario lo pida explícitamente.
- No commitear `.env`, `.agents.json`, `prueba/odoo_simulado.json`, `prueba/compartido/`, `compartido/` ni bitácoras. Los pedidos van sólo a la rama `cola`.
- Los datos de `prueba/datos/` son ficticios. Para cambiarlos, editar `prueba/generar_datos.py` y regenerar.
- Pruebas sin red: `python -m pytest -q`. Tienen que pasar antes de commitear.
- Textos para usuarios en español rioplatense.

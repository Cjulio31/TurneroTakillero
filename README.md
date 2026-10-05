# Turnos Desktop

Aplicativo de escritorio (Python + PySide6) que recibe turnos desde un HUB/HOOB, los persiste en
SQLite, los envía por serial (`99 55 <turno>` x2) y los imprime. Ver `PLAN_DE_TRABAJO.md`.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py          # abre la aplicación
pytest                 # pruebas
ruff check .           # lint
```

## Empaquetado

`powershell -File packaging\build.ps1` (en Windows) genera `installer/Output/TurnosDesktopSetup.exe`.
Ver [docs/EMPAQUETADO.md](docs/EMPAQUETADO.md).

Variable opcional `TURNOS_HOME` para cambiar la ubicación de `database/` y `logs/`.

## Estado

- [x] Fase 1 — Base (estructura, logging, SQLite, configuración)
- [x] Fase 2 — UI (datos reales de SQLite; HUB/serial/impresora aún simulados)
- [x] Fase 3 — Mock HUB (`HubClient`, `MockHubClient`, `HubService` con backoff, panel “Mock HUB”)
- [x] Fase 4 — TurnService (validación, idempotencia, estados, recuperación, sincronización de ACK)
- [x] Fase 5 — Serial (`TurnProtocol`, `SerialService`, reconexión; probar sin hardware con el puerto `loop://`)
- [x] Fase 6 — Impresión (genérica vía impresora de Windows; falta el método del hardware real)
- [ ] Fase 7 — HUB real
- [ ] Fase 8 — Integración
- [~] Fase 9 — Empaquetado (listo para construir; falta la prueba en Windows limpio)

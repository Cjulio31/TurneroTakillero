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

Variable opcional `TURNOS_HOME` para cambiar la ubicación de `database/` y `logs/`.

## Estado

- [x] Fase 1 — Base (estructura, logging, SQLite, configuración)
- [x] Fase 2 — UI (datos reales de SQLite; HUB/serial/impresora aún simulados)
- [x] Fase 3 — Mock HUB (`HubClient`, `MockHubClient`, `HubService` con backoff, panel “Mock HUB”)
- [x] Fase 4 — TurnService (validación, idempotencia, estados, recuperación, sincronización de ACK)
- [ ] Fase 5 — Serial
- [ ] Fase 6 — Impresión
- [ ] Fase 7 — HUB real
- [ ] Fase 8 — Integración
- [ ] Fase 9 — Empaquetado

# Turnos Desktop

Aplicativo de escritorio (Python + PySide6) que recibe turnos desde un HUB/HOOB, los persiste en
SQLite, los envía por serial (`99 55 <turno>` x2) y los imprime. Ver `PLAN_DE_TRABAJO.md`.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py          # bootstrap (Fase 1: crea BD y logs)
pytest                 # pruebas
ruff check .           # lint
```

Variable opcional `TURNOS_HOME` para cambiar la ubicación de `database/` y `logs/`.

## Estado

- [x] Fase 1 — Base (estructura, logging, SQLite, configuración)
- [ ] Fase 2 — UI
- [ ] Fase 3 — Mock HUB
- [ ] Fase 4 — TurnService
- [ ] Fase 5 — Serial
- [ ] Fase 6 — Impresión
- [ ] Fase 7 — HUB real
- [ ] Fase 8 — Integración
- [ ] Fase 9 — Empaquetado

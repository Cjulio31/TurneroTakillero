# CLAUDE.md

Guía para trabajar en este repositorio. Idioma del proyecto: documentación y UI en español;
código (nombres, commits) en inglés/español técnico consistente con lo existente.

## Qué es

**Turnos Desktop**: aplicativo de escritorio (Python 3.11+ / PySide6) que es el cliente operativo de
una terminal de turnos. Recibe turnos desde un HUB/HOOB, los valida, los persiste en SQLite, los
envía a un dispositivo serial (`99 55 <turno>` ×2) y los imprime. **No genera turnos.**
Plan y fases: `PLAN_DE_TRABAJO.md`. La especificación completa vive en ese plan y en el README.

## Comandos

```bash
pip install -r requirements-dev.txt
python run.py            # ejecuta la app
python -m pytest -q      # pruebas (usar `python -m pytest`, no el binario `pytest` suelto)
ruff check . --fix && ruff format .   # lint + formato (obligatorio antes de commit)
```

- Las pruebas de Qt corren sin pantalla: `tests/conftest.py` fija `QT_QPA_PLATFORM=offscreen`.
- En Linux headless pueden faltar librerías de Qt (`libegl1`, `libgl1`, `libxkbcommon0`, ...).
- `TURNOS_HOME` cambia la carpeta base de `database/` y `logs/`.

## Arquitectura (capas)

`UI (PySide6) → Controllers → Services → HUB / Serial / Impresora / SQLite`

- `app/ui/`: solo widgets. **Nunca** lógica de HUB, serial o impresora; llaman a controladores.
- `app/controllers/`: puente UI↔servicios. `AppState` (QObject) es el estado compartido
  (estado de hub/serial/impresora/BD) que los servicios actualizan y la UI observa por señales.
- `app/services/`: `HubService`, `ConfigurationService` (hechos); `TurnService`, `SerialService`,
  `PrinterService`, `HealthService` (pendientes).
- `app/communication/`: transportes del HUB detrás de la interfaz `HubClient`
  (`MockHubClient` hoy; `WebSocketHubClient` / `RestHubClient` en la Fase 7). Cambiar de transporte
  no debe tocar `TurnService`.
- `app/protocol/`, `app/hardware/`: protocolo serial y dispositivos (Fases 5–6).
- `app/database/`: SQLite (tablas `turns`, `configuration`, `events`) + repositorios.
- `app/context.py`: `AppContext` agrupa db, servicios base y `AppState`.

## Reglas críticas (no romper)

1. **Idempotencia**: `turns.message_id` es `UNIQUE`. Un mensaje duplicado nunca se vuelve a
   imprimir ni a enviar por serial. `TurnRepository.add` devuelve `None` si ya existe.
2. **Persistir antes de procesar**: el turno se guarda como `RECEIVED` en SQLite apenas llega;
   nunca depender solo de RAM. Un turno no se pierde por fallos de serial/impresora/HUB.
3. **Estados**: `RECEIVED → PROCESSING → SENT → PRINTED → COMPLETED`, o `ERROR`. Un `COMPLETED`
   jamás se reenvía ni se reprocesa.
4. **Recuperación tras reinicio**: consultar `RECEIVED/PROCESSING/ERROR` y aplicar política
   explícita; no reprocesar a ciegas.
5. **Protocolo serial**: `0x99 0x55 <turno 1 byte>`, enviado 2 veces. **No agregar CRC, checksum,
   ACK ni bytes extra** hasta confirmar con el hardware. Sin reintento serial ciego (ambigüedad
   sin ACK). El turno es 1–255.
6. **Hilos**: la UI nunca se bloquea. HUB real, serial, impresión y reconexión van en
   `QThread`/workers con signals/slots. (El Mock actual es síncrono y no bloquea.)
7. **Errores**: nunca `except: pass`. Capturar, registrar (`logging`), actualizar estado y
   conservar datos para reintentar.
8. **Seguridad**: HTTPS/WSS para HUB remoto; el token no debe quedar en texto plano
   (hoy se guarda en la tabla `configuration`; migrar a `keyring`/DPAPI antes de la Fase 7).
9. **Prueba de turno** en Diagnóstico no crea turnos reales ni afecta la secuencia.

## Convenciones

- Python 3.11+, type hints, `ruff` (línea 100). Modelos como `dataclass`.
- Logs con `logging` estándar (`logs/app.log`, `RotatingFileHandler` 5 MB × 5).
- Reconexión HUB con backoff 5/10/20/30/60 s (máx. 60), `BackoffPolicy`.
- Los mensajes del HUB llegan como `dict` crudo; `TurnService` (Fase 4) los valida y convierte a
  `TurnMessage`.
- Cada fase añade pruebas. Mantener `ruff check` y `python -m pytest` en verde antes de commitear.
- No usar Flask ni interfaz web. Sin dependencias del navegador.

## Estado de fases

- [x] 1 Base · [x] 2 UI · [x] 3 Mock HUB
- [ ] 4 TurnService · [ ] 5 Serial · [ ] 6 Impresión · [ ] 7 HUB real · [ ] 8 Integración
  · [ ] 9 Empaquetado

## Pendientes externos (ver PLAN_DE_TRABAJO.md §2)

Protocolo/credenciales del HUB real, modelo de impresora, comportamiento del dispositivo serial
(¿ACK?), política de recuperación de `PROCESSING`, tope de turno 255.

## Git

Desarrollar en la rama `claude/optimistic-meitner-bxs4yy`. No abrir Pull Requests salvo petición
explícita.

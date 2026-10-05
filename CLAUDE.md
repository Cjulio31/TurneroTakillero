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
- `app/services/`: `HubService`, `TurnService`, `ConfigurationService` (hechos); `SerialService`,
  `PrinterService`, `HealthService` (hechos). `HealthService` agrega el estado de los 4
  componentes + turnos pendientes/en error en un `HealthReport` (OK/DEGRADED/DOWN) que alimenta la
  bandeja y el Inicio; mide la BD (`ping` cada 10 s, `integrity_check` al arrancar). `TurnService` depende solo de los puertos
  `TurnSerialPort` / `TicketPrinter` (`services/ports.py`) y de `errors.py`.
- `app/communication/`: transportes del HUB detrás de la interfaz `HubClient`
  (`MockHubClient`, `WebSocketHubClient`, `RestHubClient`; `factory.create_hub_client` elige por la URL:
  vacía=mock, `wss`=WebSocket, `https`=REST; solo HTTPS/WSS salvo localhost, `hub_url.ensure_secure_url`).
  El formato de cuadros es PROVISIONAL y vive en `hub_protocol.py` (ver `docs/HUB_PROTOCOLO.md`).
  Los transportes de red usan hilos propios (`connect_blocks=True`): `HubService` conecta en
  `QThreadPool` y reenvía los callbacks al hilo de la UI por señales. Cambiar de transporte no
  debe tocar `TurnService`.
- `app/protocol/`: `message_validator.py` (mensajes del HUB) y `turn_protocol.py` (`TurnProtocol`,
  paquete serial). `app/hardware/`: `serial_device.py` (envoltorio de pyserial + `SerialSettings`);
  `printer_backend.py` (backends: simulado si `printer_type` vacío, `Windows Printer` vía Qt, USB/Serial/Red
  aún `UnsupportedBackend` hasta tener el modelo real) y `ticket.py` (contenido del ticket).
- `app/database/`: SQLite (tablas `turns`, `configuration`, `events`) + repositorios.
- `app/context.py`: `AppContext` agrupa db, servicios base y `AppState`.

## Reglas críticas (no romper)

1. **Idempotencia**: `turns.message_id` es `UNIQUE`. Un mensaje duplicado nunca se vuelve a
   imprimir ni a enviar por serial. `TurnRepository.add` devuelve `None` si ya existe.
2. **Persistir antes de procesar**: el turno se guarda como `RECEIVED` en SQLite apenas llega;
   nunca depender solo de RAM. Un turno no se pierde por fallos de serial/impresora/HUB.
3. **Estados**: `RECEIVED → PROCESSING → SENT → PRINTED → COMPLETED`, o `ERROR`. Un `COMPLETED`
   jamás se reenvía ni se reprocesa. `PENDING_STATUSES` = todo menos `COMPLETED`.
   Serial no disponible (nada enviado) → el turno vuelve a `RECEIVED` y se procesa al volver el
   serial. Error de impresión → `ERROR`; el reintento NO reenvía el serial (`sent_at` ya existe).
   Error de envío serial incierto (`SerialSendError`) → `ERROR`, sin reintento automático.
4. **Recuperación tras reinicio** (`TurnService.recover_on_startup`): `PROCESSING`/`SENT` → `ERROR`
   (`INTERRUPTED`, verificación manual); `PRINTED` → `COMPLETED`; `RECEIVED` se procesa; `ERROR` queda
   para reintento manual. Nunca reprocesar a ciegas.
5. **Protocolo serial** (`TurnProtocol`, `SerialService`): `0x99 0x55 <turno 1 byte>`, enviado 2 veces. **No agregar CRC, checksum,
   ACK ni bytes extra** hasta confirmar con el hardware. Sin reintento serial ciego (ambigüedad
   sin ACK). El turno es 1–255. Sin puerto o con el puerto desaparecido (se verifica antes de
   escribir) → `SerialUnavailableError` (nada enviado, turno pendiente); fallo durante la escritura →
   `SerialSendError` (incierto → `ERROR`). `SerialService` reconecta solo (backoff 2/5/10/20/30 s),
   abre el puerto en un `QThreadPool` y reabre al cambiar la configuración de conexión.
   Para probar sin hardware: puerto `loop://` (pyserial) en la pantalla Hardware.
6. **Hilos**: la UI nunca se bloquea. HUB real, serial, impresión y reconexión van en
   `QThread`/workers con signals/slots. Estado actual: la apertura/reconexión del serial va en
   `QThreadPool`; `send_turn` y `TurnService` son síncronos en el hilo principal (3 bytes con
   timeout de 1 s). Mover `TurnService` a un worker (con su propia conexión SQLite) queda para
   la Fase 8 si el hardware real lo exige.
7. **Errores**: nunca `except: pass`. Capturar, registrar (`logging`), actualizar estado y
   conservar datos para reintentar.
8. **Seguridad**: HTTPS/WSS para HUB remoto. El token del HUB vive en el almacén del sistema
   (`keyring`: Credential Manager en Windows), nunca en SQLite: `ConfigurationService` usa
   `SecretStore` (`services/secret_store.py`) y migra al leer un token en texto plano heredado.
   Si el almacén falla, guardar la configuración lanza `SecretStoreError` (no se guarda a medias).
9. **Prueba de turno** en Diagnóstico no crea turnos reales ni afecta la secuencia.

## Convenciones

- Python 3.11+, type hints, `ruff` (línea 100). Modelos como `dataclass`.
- Logs con `logging` estándar (`logs/app.log`, `RotatingFileHandler` 5 MB × 5).
- Reconexión HUB con backoff 5/10/20/30/60 s (máx. 60), `BackoffPolicy`.
- Los mensajes del HUB llegan como `dict` crudo; `TurnService` los valida (`parse_message`) y
  convierte a `TurnMessage`. Turno válido: entero 1–255 (>255 se rechaza). Los rechazos se registran
  en `events` y se informan al HUB como `REJECTED` si traen `message_id`.
- Confirmaciones al HUB: `turns.ack_status/acked_at` registran qué estado final conoce el HUB;
  `sync_pending_acks()` (al quedar el HUB `READY`) informa lo pendiente sin reprocesar turnos.
- SQLite: `TurnService` corre síncrono en el hilo principal. Si las fases 5-6 usan hilos, cada hilo
  necesita su propia conexión (`Database`) o los resultados deben volver al hilo principal por
  signals. Las migraciones de columnas van en `Database._migrate`.
- Cada fase añade pruebas. Mantener `ruff check` y `python -m pytest` en verde antes de commitear.
- No usar Flask ni interfaz web. Sin dependencias del navegador.

## Estado de fases

- [x] 1 Base · [x] 2 UI · [x] 3 Mock HUB · [x] 4 TurnService · [x] 5 Serial · [x] 6 Impresión (genérica; falta el método del hardware real)
- [~] 7 HUB real (transportes listos y probados con HUB local; falta el contrato real) · [ ] 8 Integración
  · [~] 9 Empaquetado (archivos listos; falta probar en Windows limpio)

## Empaquetado

Ver `docs/EMPAQUETADO.md`. PyInstaller `onedir` (`packaging/turnos_desktop.spec`) + Inno Setup
(`installer/TurnosDesktop.iss`); `packaging/build.ps1` hace todo. Empaquetado, los datos van a
`%LOCALAPPDATA%\TurnosDesktop` (`constants.resolve_base_dir`), nunca junto al exe. `--self-check`
verifica el exe sin abrir la ventana. Subir `APP_VERSION` antes de cada release; no cambiar el `AppId`.

## Pendientes externos (ver PLAN_DE_TRABAJO.md §2)

Protocolo/credenciales del HUB real, modelo de impresora, comportamiento del dispositivo serial
(¿ACK?). Decididos en la Fase 4: recuperación de `PROCESSING` → `ERROR`; turno >255 rechazado.

## Git

Desarrollar en la rama `claude/optimistic-meitner-bxs4yy`. No abrir Pull Requests salvo petición
explícita.

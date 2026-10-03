# Plan de trabajo — Turnos Desktop (Python + PySide6 + HUB/HOOB)

Base: Especificación Técnica del aplicativo de escritorio de turnos.
Principio: el Desktop **recibe, valida, persiste, envía por serial e imprime**; no genera turnos.

## 1. Alcance y decisiones ya tomadas

- Python 3.11+, PySide6 (sin Flask ni web), SQLite, pyserial, PyInstaller + instalador.
- Arquitectura por capas: UI → Controllers → Services → (HUB / Serial / Impresora / SQLite).
- La UI **nunca** contiene lógica de HUB, serial o impresora.
- Protocolo serial fijo: `0x99 0x55 <turno>` enviado 2 veces; sin CRC/ACK hasta confirmar con el hardware.
- Idempotencia por `message_id` (`UNIQUE`). Persistir antes de procesar.
- `MockHubClient` hasta tener el HUB real.

## 2. Pendientes externos (bloqueantes y riesgos)

| # | Pendiente | Bloquea | Responsable | Acción |
|---|-----------|---------|-------------|--------|
| 1 | Datos del HUB: URL, protocolo (REST/WS/MQTT), auth, formato de mensaje, ACK, heartbeat, duplicados, ambientes, errores (sección 57 de la spec) | Fase 7 | Equipo HUB | Enviar checklist y fijar fecha |
| 2 | Modelo de impresora y método (USB/Serial/Windows/Red) | Fase 6 | Cliente / hardware | Obtener modelo real y driver |
| 3 | Comportamiento del dispositivo serial: ¿ACK/NACK, checksum, ID? | Política de reintento serial | Hardware | Documentar; mientras tanto no reintentar a ciegas |
| 4 | Política de recuperación de turnos en `PROCESSING` tras reinicio | Fase 4 | Negocio + dev | Definir (propuesta: marcar `ERROR` y pedir intervención manual) |
| 5 | Rango del turno: 1 byte limita a 0–255 | Validación | Negocio | Confirmar si hay reinicio diario / tope 255 |
| 6 | Almacenamiento seguro del token (no texto plano) | Fase 1/7 | Dev | Usar Windows Credential Manager (`keyring`) o DPAPI |

## 3. Fases

Estimaciones en días hábiles de una persona; ajustar al equipo.

### Fase 1 — Base del proyecto (3 d)
- Estructura de carpetas de la spec, `requirements.txt`, `run.py`, `.gitignore`, README.
- `logger.py` con `RotatingFileHandler` (5 MB × 5), `constants.py`, `validators.py`.
- `database.py`: creación de tablas `turns`, `configuration`, `events` (migración inicial); repositorios.
- `ConfigurationService` + `config_repository`.
- Configurar lint/format/tests (ruff, pytest, pytest-qt).
- **Entregable:** app arranca, crea BD y logs. **Criterio:** tests de repositorios pasan.

### Fase 2 — UI (5 d)
- `main_window` con menú: Inicio, Turnos, Historial, Configuración, Hardware, Diagnóstico, Acerca de.
- Dashboard (último turno, estado HUB/Serial/Impresora, últimos tiempos).
- Pantallas de configuración (HUB, serial, impresora, logs), historial con filtros (fecha, turno, estado), diagnóstico.
- System tray (Abrir / Estado / Configuración / Salir); seguir escuchando minimizada.
- **Criterio:** UI navegable con datos simulados, sin lógica de comunicación dentro de la UI.

### Fase 3 — Mock HUB (3 d)
- Interfaz `HubClient` (`connect`, `disconnect`, `send_ack`, `on_turn_received`, `is_connected`).
- `MockHubClient` + ventana de control: enviar, reenviar (duplicado), error, desconectar/reconectar, ráfaga de turnos.
- Reconexión con backoff 5/10/20/30/60 s (máx. 60).
- **Criterio:** se pueden simular todos los escenarios de la sección 51.

### Fase 4 — TurnService (5 d)
- `TurnMessage` / modelos y validación en cadena (message_id, terminal_id, terminal correcta, turno válido, duplicado).
- Persistencia inmediata en `RECEIVED`; máquina de estados `RECEIVED → PROCESSING → SENT → PRINTED → COMPLETED` / `ERROR`.
- Idempotencia: duplicado se ignora y se confirma el estado previo.
- Recuperación al iniciar: consultar `RECEIVED/PROCESSING/ERROR` y aplicar política definida (sin reprocesar a ciegas).
- Cola local y sincronización al reconectar (nunca reenviar un `COMPLETED`).
- **Criterio:** pruebas de duplicados, desconexión durante proceso y reinicio (secciones 52–54) en verde.

### Fase 5 — Serial (4 d)
- `TurnProtocol.build_packet` (`99 55 NN`), 2 transmisiones configurables, log hexadecimal `TX: 99 55 19`.
- `SerialService`: `connect/disconnect/send/is_connected/reconnect/get_status`; selección de puerto (COMx).
- Reconexión automática; el turno queda pendiente si no hay puerto.
- Worker en `QThread`; **sin reintento ciego** (riesgo #3).
- **Criterio:** pruebas con puerto virtual (com0com / socat) y con el dispositivo real.

### Fase 6 — Impresión (4 d, depende del pendiente #2)
- `PrinterService` (`print_ticket`, `test`, `is_available`), implementación solo para el método del hardware real.
- Diseño del ticket, error de impresión → estado `ERROR` conservando `message_id`, botón **Reintentar**.
- Turno de prueba y prueba de impresora (sin afectar secuencia de producción).
- **Criterio:** caso "impresora desconectada" (sección 55) y reintento funcionan.

### Fase 7 — HUB real (5 d, depende del pendiente #1)
- `WebSocketHubClient` (eventos) y `RestHubClient` (registro, config, confirmaciones), autenticación, heartbeat PING/PONG.
- HTTPS/WSS; token en almacenamiento seguro.
- Mapeo del formato real al `TurnMessage` sin tocar `TurnService`.
- **Criterio:** terminal se registra, mantiene conexión, recibe y confirma turnos contra ambiente de pruebas.

### Fase 8 — Integración y hardening (4 d)
- Prueba extremo a extremo: aplicativo externo → HUB → Desktop → Serial → Impresora.
- Pruebas de carga ligera, desconexiones, cortes de energía, reinicio con turnos pendientes.
- Revisión de manejo de errores (sin `except: pass`), logs y modo offline.

### Fase 9 — Empaquetado e instalación (3 d)
- `TurnosDesktop.exe` con PyInstaller; instalador `TurnosDesktopSetup.exe` (Inno Setup/NSIS).
- Opción "iniciar con Windows", BD y config iniciales, recursos.
- Prueba de instalación limpia en Windows sin Python.

**Total estimado:** ~36 días hábiles (≈7–8 semanas con una persona; menos si UI y serial se paralelizan).

## 4. Hitos

| Hito | Fin de fase | Resultado |
|------|-------------|-----------|
| M1 | 3 | Base técnica lista |
| M2 | 4 | Flujo completo con Mock HUB (recibir → persistir → idempotencia) |
| M3 | 6 | Serial + impresión reales con Mock |
| M4 | 7 | Conexión al HUB real |
| M5 | 9 | Instalador entregable y aceptación |

## 5. Estrategia de pruebas

- Unitarias: validaciones, `TurnProtocol`, repositorios, máquina de estados.
- Integración: `TurnService` con Mock HUB + serial/impresora falsos.
- Críticas obligatorias: duplicados (no imprimir dos veces), desconexión tras recepción, reinicio en `PROCESSING`, impresora desconectada, serial desconectado.
- Manual en hardware real antes de M3 y M5.

## 6. Criterios de aceptación

Los de la sección 59 de la spec. Resumen: app nativa, conexión persistente y reconexión, validación + idempotencia, persistencia SQLite, serial `99 55 + turno` ×2, impresión con reintento, tolerancia a desconexión de HUB/serial/impresora, logs, historial, diagnóstico, configuración, segundo plano, inicio automático y `.exe`.

## 7. Riesgos principales

1. **HUB sin definir** → mitigado con `MockHubClient` y interfaz `HubClient`.
2. **Reintento serial ambiguo** (sin ACK) → política explícita antes de automatizar.
3. **Hardware de impresora desconocido** → no iniciar Fase 6 sin modelo.
4. **Turno de 1 byte** (máx. 255) → definir comportamiento al exceder.
5. **Bloqueo de UI** → todo I/O en `QThread` con señales/slots.
6. **Credenciales** → no guardar en texto plano.

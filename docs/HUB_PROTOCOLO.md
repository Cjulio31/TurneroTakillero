# Conexión con el HUB (Fase 7)

Cómo se conecta Turnos Desktop al HUB/HOOB y qué formato de mensajes usa.

> **IMPORTANTE — formato provisional.** El equipo del HUB aún no entregó su especificación
> (pendiente externo #1 del plan). Los transportes, la reconexión, la seguridad y las pruebas
> están hechos y verificados contra servidores locales, pero **los nombres de rutas y cuadros de
> abajo son una suposición razonable**, no el contrato real. Cuando llegue la especificación solo
> hay que ajustar `app/communication/hub_protocol.py` (WebSocket) y las rutas de
> `app/communication/rest_hub_client.py` (REST); `TurnService` y la UI no cambian.

## 1. Cómo se elige el transporte

Según la **URL del HUB** en Configuración (no hay un selector aparte):

| URL | Transporte |
|---|---|
| vacía | HUB simulado (desarrollo y capacitación; aparece la pantalla *Mock HUB*) |
| `wss://…` | WebSocket (el HUB empuja los turnos) |
| `https://…` | REST (la terminal consulta turnos cada 3 s) |

Los cambios de URL, token o terminal **se aplican al reiniciar** la aplicación.

## 2. Seguridad

- Solo **HTTPS/WSS**. `http://` y `ws://` se aceptan únicamente hacia `localhost`/`127.0.0.1`
  (pruebas). Una URL remota sin cifrar se rechaza al guardar la configuración, y si ya estaba
  guardada la app arranca con el HUB simulado y deja un evento de error.
- El token viaja en `Authorization: Bearer <token>` y se guarda en el almacén seguro de Windows,
  nunca en SQLite (ver regla 8 de `CLAUDE.md`).
- Los certificados TLS se verifican siempre; no hay opción para desactivarlo.

## 3. Comportamiento común (ya implementado)

- **Reconexión automática** con backoff 5 / 10 / 20 / 30 / 60 s (`HubService`), con la conexión
  en un hilo aparte: la interfaz nunca se bloquea.
- Al conectar: registra la terminal y envía `READY`; el estado pasa a **LISTO**.
- Los turnos se guardan en SQLite al llegar; un mensaje repetido (mismo `message_id`) no se
  vuelve a imprimir ni a enviar (idempotencia).
- Las confirmaciones (`ACK`) pendientes, por ejemplo de turnos terminados con el HUB caído, se
  reenvían solas al reconectar (`sync_pending_acks`).
- **Heartbeat:** el WebSocket usa ping de protocolo cada 20 s (timeout 10 s) y además contesta
  `PING` con `PONG`. Una caída se detecta en menos de ~30 s.
- *Diagnóstico → Probar HUB*: informa el transporte y el estado, y reintenta al instante.

## 4. WebSocket (provisional)

Cada cuadro es un objeto JSON con `type`.

Terminal → HUB:

| `type` | Campos | Cuándo |
|---|---|---|
| `REGISTER` | `terminal_id`, `name`, `location`, `app_version`, `protocol` | al abrir el canal |
| `READY` | `terminal_id` | tras registrarse |
| `ACK` | `terminal_id`, `message_id`, `status` | al terminar un turno (`COMPLETED`, `ERROR`, `REJECTED`) |
| `PONG` | — | respuesta a `PING` |

HUB → terminal:

| `type` | Campos | Significado |
|---|---|---|
| `TURN` | `data`: `{message_id, terminal_id, turn, priority?, created_at?, metadata?}` | turno nuevo |
| `PING` | — | latido |
| `ERROR` | `code`, `message` | error informado por el HUB |
| `REGISTERED` | — | acuse de registro (opcional; no se espera) |

Los cuadros que no son JSON, no traen `type` o son desconocidos se ignoran con un log.

## 5. REST (provisional)

Rutas relativas a la URL base configurada:

| Método y ruta | Uso |
|---|---|
| `POST /terminals/{terminal_id}/register` | registro (`terminal_id`, `name`, `location`, `app_version`) |
| `GET /terminals/{terminal_id}/messages` | lista JSON de mensajes pendientes; se consulta cada 3 s |
| `POST /messages/{message_id}/ack` | `{terminal_id, status}` |

`401/403` se informa como «Autenticación rechazada». Un mensaje puede llegar repetido hasta que
se confirma: es seguro por la idempotencia. Si una consulta falla se considera caída la conexión
y se reconecta con backoff.

## 6. Qué necesitamos del equipo del HUB

Lista a confirmar (ver también `PLAN_DE_TRABAJO.md` §2, pendiente #1):

1. URL y ambientes (pruebas / producción) y si es WebSocket, REST o ambos.
2. Autenticación: ¿Bearer token, API key en otro encabezado, o en la URL?
3. Formato real de cada mensaje (registro, turno, ACK, heartbeat, errores).
4. ¿El HUB reenvía lo no confirmado al reconectar? ¿Qué `status` espera en el ACK?
5. Heartbeat: intervalo y quién lo inicia.
6. Códigos de error y qué debe hacer la terminal con cada uno.

## 7. Pruebas

`tests/test_hub_transports.py` levanta un HUB WebSocket (`websockets`) y uno REST
(`http.server`) reales en `127.0.0.1` y comprueba: registro y token, recepción de turnos,
ACK/READY, PING/PONG, caída y reconexión, URL insegura, y el flujo completo a través de
`HubService`. Cuando se tenga el ambiente de pruebas del HUB real, falta la prueba de
integración contra él (criterio de la Fase 7).

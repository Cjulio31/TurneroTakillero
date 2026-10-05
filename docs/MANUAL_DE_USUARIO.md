# Manual de usuario — Turnos Desktop

Guía para quien opera la terminal de turnos. No requiere conocimientos técnicos. Para instalar
el programa ver [EMPAQUETADO.md](EMPAQUETADO.md).

> **Versión de este manual:** corresponde a la versión 0.1.0. Por ahora el programa trabaja con
> un **HUB simulado** (de pruebas); la conexión con el HUB real y la impresora definitiva se
> habilitarán en versiones posteriores. Las secciones lo indican donde aplica.

## 1. ¿Qué hace el programa?

Turnos Desktop es la terminal que atiende los turnos de su sede. Por cada turno que llega:

1. Lo **recibe** del HUB y lo **guarda** en el equipo (no se pierde aunque se apague el PC).
2. Lo **envía al dispositivo serial** (el display o pantalla de turnos).
3. Lo **imprime** en un ticket.
4. **Confirma** al HUB que terminó.

El programa **no genera turnos**: los turnos los crea otro sistema y llegan a esta terminal.
Un mismo turno nunca se imprime ni se envía dos veces, aunque el HUB lo repita.

## 2. Abrir y cerrar el programa

- Se abre desde el menú Inicio (**Turnos Desktop**) o, si se activó al instalar, **arranca solo
  al encender Windows**.
- Al **cerrar la ventana (X) el programa sigue funcionando** en la bandeja del sistema (junto al
  reloj), porque debe seguir recibiendo turnos. Para abrirlo de nuevo: clic en su icono.
- Para **salir de verdad**: clic derecho en el icono de la bandeja → **Salir**. Mientras esté
  cerrado no se atienden turnos nuevos.

### El icono de la bandeja

| Color | Significado |
|---|---|
| Verde | Todo en orden |
| Ámbar | Funciona, pero algo requiere atención (por ejemplo, impresora no disponible o turnos en error) |
| Rojo | Falla la base de datos: avise a soporte |

Al pasar el mouse sobre el icono se lee el motivo. Con clic derecho: **Abrir**, **Configuración**
y **Salir**.

## 3. La ventana principal

El menú de la izquierda tiene estas pantallas: **Inicio, Turnos, Historial, Configuración,
Hardware, Diagnóstico y Acerca de**. (En modo de pruebas aparece también **Mock HUB**.)

### 3.1 Inicio

Es la pantalla de trabajo diario:

- **Número grande**: el último turno recibido, con su estado debajo.
- **Indicadores**: HUB, Serial, Impresora y Base de datos. Verde = bien; ámbar = conectando;
  rojo = problema; gris = sin datos todavía.
- **Último recibido / Último impreso**: hora de cada uno.
- **Pendientes y En error**: cuántos turnos faltan por completar y cuántos fallaron.

Estados de un turno:

| Estado | Significa |
|---|---|
| RECIBIDO | Llegó y está guardado; espera su turno de procesamiento |
| PROCESANDO | Se está enviando al dispositivo |
| ENVIADO | Ya se mandó al dispositivo; falta imprimir |
| IMPRESO | Ticket impreso; falta confirmar al HUB |
| COMPLETADO | Terminado y confirmado |
| ERROR | Falló; requiere revisión (ver §3.2) |

### 3.2 Turnos (pendientes y reintento)

Lista los turnos **no completados**: número, identificador, estado y mensaje de error.

Para **reintentar** un turno en ERROR: selecciónelo en la tabla y pulse **REINTENTAR**. Solo se
pueden reintentar los turnos en ERROR. **Actualizar** recarga la lista.

Cómo actúa el programa ante fallas (lo hace solo, usted no tiene que intervenir):

- **Sin conexión al dispositivo serial:** el turno queda en RECIBIDO y se procesa
  automáticamente cuando el serial vuelve. No requiere reintento manual.
- **Falla de impresión** (sin papel, impresora apagada…): el turno pasa a ERROR. Arregle la
  impresora y pulse **REINTENTAR**: **se vuelve a imprimir sin reenviar** el turno al dispositivo.
- **Error al escribir en el serial** (el resultado es incierto, no se sabe si llegó): pasa a
  ERROR y **no se reintenta solo**, para no mostrar el turno dos veces. Compruebe en el
  dispositivo si el turno apareció y, solo si no apareció, pulse **REINTENTAR**.
- **Programa cerrado o equipo apagado en pleno proceso:** al volver a abrirlo, los turnos que
  estaban a medias (PROCESANDO/ENVIADO) quedan en ERROR para que usted verifique; los ya
  impresos se completan; los recibidos se procesan.

> Un turno **COMPLETADO** nunca se vuelve a procesar.

### 3.3 Historial

Consulta de todos los turnos. Filtros: **Fecha** (marque la casilla para activarla), **Turno**
(0 = todos) y **Estado**; pulse **Buscar**. Columnas: Fecha, Hora, Turno, Message ID, Estado,
Origen (terminal) y Error.

### 3.4 Configuración (HUB y terminal)

| Campo | Para qué sirve |
|---|---|
| URL HUB | Dirección del HUB (`https://…`; debe comenzar con `http(s)://` o `ws(s)://`) |
| Token / API Key | Credencial que entrega el equipo del HUB |
| Timeout | Segundos de espera por respuesta del HUB (1–300) |
| Intervalo de reconexión | Segundos entre reintentos de conexión (1–60) |
| Terminal ID | Identificador único de esta terminal (obligatorio si hay URL) |
| Nombre / Ubicación | Aparecen en el encabezado del ticket |

Pulse **Guardar**. Los cambios del HUB se aplican al reconectar.

- El **token** se guarda de forma segura en Windows (Administrador de credenciales), no en
  texto plano. Si Windows no permite guardarlo, aparece «No guardado: …».
- Si el HUB se cae, el programa **reconecta solo** (esperas crecientes hasta 60 s). Los turnos
  recibidos no se pierden.

### 3.5 Hardware (serial e impresora)

**Serial** — parámetros del dispositivo de turnos:

| Campo | Valor habitual |
|---|---|
| Puerto | `COM3`, `COM4`… (use **Actualizar puertos** si conectó el cable después de abrir) |
| Baudrate | 9600 |
| Data bits / Paridad / Stop bits | 8 / None / 1 |
| Transmisiones | 2 (cuántas veces se envía cada turno) |

Use los valores que indique el proveedor del dispositivo. Al cambiar el puerto o los parámetros,
la conexión se reabre sola.

**Impresora** — campo *Método*:

| Método | Estado |
|---|---|
| (sin definir) | Modo simulado: no imprime, solo registra (para pruebas) |
| **Windows Printer** | **Disponible.** Escriba en *Puerto / nombre* el nombre exacto de la impresora instalada en Windows; vacío = la impresora predeterminada |
| USB, Serial, Network Printer | Aún no disponibles (dependen del modelo de impresora) |

Pulse **Guardar** en cada sección.

### 3.6 Diagnóstico

Para comprobar cada parte y buscar la causa de un problema:

- **Probar Serial:** informa si está conectado; si no, intenta reconectar.
- **Probar impresora:** imprime un **ticket de prueba** («PRUEBA DE IMPRESORA», sin validez).
- **Probar base de datos:** verifica que los datos se pueden leer.
- **Enviar turno de prueba:** manda el número elegido (1–255) directamente al dispositivo para
  ver que lo muestra. **No crea un turno real ni altera la secuencia ni el historial.**
- **Ver logs:** muestra las últimas líneas del registro de actividad (útil para soporte).
- **Borrar logs:** elimina el registro de actividad (pide confirmación). **Solo borra los logs**:
  los turnos, el historial y la configuración no se tocan. Antes de borrar, guarde una copia de
  `logs\app.log` si soporte la necesita para analizar un problema.
- **Probar HUB:** todavía no disponible (llegará con el HUB real).

El resultado aparece debajo con ✔ (bien) o ✖ (falló y por qué).

> **Probar sin el dispositivo físico:** en *Hardware* escriba `loop://` como puerto serial.
> El programa funcionará como si hubiera dispositivo (sin enviar nada fuera).

### 3.7 Acerca de

Muestra la versión y la carpeta donde se guardan los datos. Tenga a mano la versión al llamar a
soporte.

### 3.8 Mock HUB (solo pruebas)

Mientras el HUB real no esté conectado, esta pantalla simula al HUB: **ENVIAR** (un turno),
**REENVIAR** (duplicado: no debe imprimirse otra vez), **ENVIAR VARIOS**, **MENSAJE INVÁLIDO**,
**ERROR**, **DESCONECTAR/RECONECTAR** y la casilla «HUB disponible». Sirve para capacitar y
probar; **no aparece cuando se use el HUB real**.

## 4. Flujo normal de un turno

1. Llega el turno → aparece en **Inicio** como RECIBIDO.
2. Se envía al dispositivo → ENVIADO y se ve en la pantalla de turnos.
3. Sale el ticket → IMPRESO.
4. Se confirma al HUB → **COMPLETADO**.

Todo ocurre en segundos y sin intervención. Si no pasa de RECIBIDO, revise los indicadores de
Inicio (serial e impresora).

## 5. Problemas frecuentes

| Qué ve | Qué hacer |
|---|---|
| Serial **DESCONECTADO** | Revise cable y puerto en *Hardware* → **Actualizar puertos**. Se reconecta solo; los turnos esperan en RECIBIDO. |
| Impresora **NO DISPONIBLE** | Encienda/conecte la impresora y revise que el nombre en *Hardware* coincida con el de Windows. |
| Turnos en **ERROR** con «PRINT_ERROR» | Corrija la impresora (papel, tapa) y pulse **REINTENTAR** en *Turnos*. |
| Turno en ERROR con «SERIAL_ERROR» | Verifique en el display si el turno apareció; si no, **REINTENTAR**. |
| Turno en ERROR con «INTERRUPTED» | El programa se cerró a mitad del proceso. Verifique en el display y en el ticket; luego **REINTENTAR** o déjelo como está según corresponda. |
| HUB **DESCONECTADO** | Revise internet y la URL/token en *Configuración*. Reconecta solo. |
| «Base de datos con error» (rojo) | Cierre el programa, **no borre archivos** y avise a soporte. |
| «No guardado: …» al guardar | Lea el motivo en pantalla (dato inválido, o Windows no permite guardar el token). |
| Cerré la ventana y no atiende turnos | Revise la bandeja: el programa sigue abierto. Si salió con *Salir*, ábralo de nuevo. |

## 6. Dónde se guardan los datos

En `%LOCALAPPDATA%\TurnosDesktop` (se abre pegando esa ruta en el Explorador de archivos):

- `database\turnos.db` — turnos, configuración y eventos.
- `logs\app.log` — registro de actividad (se rota solo).

Al **actualizar o desinstalar el programa estos datos se conservan**. No los edite ni los borre
sin indicación de soporte: pueden contener turnos pendientes. Para pedir ayuda, envíe el archivo
`logs\app.log` y la versión (*Acerca de*).

## 7. Preguntas rápidas

**¿Se pierden turnos si se va la luz o se cae internet?** No. Cada turno se guarda al llegar. Al
volver, el programa retoma lo pendiente; lo dudoso queda en ERROR para su revisión.

**¿Se puede imprimir dos veces el mismo turno?** No automáticamente. Solo con **REINTENTAR** en un
turno en ERROR, y en ese caso no se reenvía al display.

**¿Hay que dejarlo abierto?** Sí (puede estar solo en la bandeja). Si no está en ejecución, no
recibe turnos.

**¿Quién cambia la configuración del HUB y del hardware?** El personal técnico; el operador
normalmente solo usa Inicio, Turnos y Diagnóstico.

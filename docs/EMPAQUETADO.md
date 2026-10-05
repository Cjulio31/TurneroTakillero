# Empaquetado e instalación (Fase 9)

Cómo se convierte Turnos Desktop en `TurnosDesktopSetup.exe` y cómo instalarlo, actualizarlo y
probarlo en un Windows limpio (sin Python).

> **Estado:** los archivos de empaquetado están listos y el build de PyInstaller se verificó en
> Linux (incluida la autoverificación del ejecutable). **Falta la prueba de instalación limpia en
> Windows**, que solo puede hacerse allí (ver §6).

## 1. Qué se genera

| Paso | Herramienta | Entrada | Salida |
|---|---|---|---|
| 1. Ejecutable | PyInstaller (`onedir`) | `packaging/turnos_desktop.spec` | `dist/TurnosDesktop/TurnosDesktop.exe` + `_internal/` |
| 2. Autoverificación | `TurnosDesktop.exe --self-check` | el ejecutable | código de salida 0 = OK |
| 3. Instalador | Inno Setup 6 | `installer/TurnosDesktop.iss` + `dist/` | `installer/Output/TurnosDesktopSetup.exe` |

Se usa **onedir** y no onefile: arranca más rápido, no se descomprime en `%TEMP%` en cada inicio
y da menos falsos positivos de antivirus. El instalador empaqueta la carpeta completa.

## 2. Archivos

```
packaging/turnos_desktop.spec   Receta de PyInstaller (sin consola, icono, hidden imports)
packaging/build.ps1             Build completo en un comando (tests → exe → autoverificación → instalador)
installer/TurnosDesktop.iss     Script de Inno Setup
requirements-build.txt          Dependencias + PyInstaller
resources/icons/app.ico         Icono (provisional: círculo verde con "T"; reemplazar por el definitivo)
.github/workflows/windows-build.yml   Mismo build en GitHub Actions (windows-latest)
```

## 3. Construir el instalador

Se debe hacer **en Windows** (PyInstaller no compila de forma cruzada).

Requisitos: Python 3.11+ y [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`ISCC.exe`).

```powershell
python -m venv .venv ; .venv\Scripts\activate
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Opciones: `-SkipTests` (omite ruff y pytest) y `-SkipInstaller` (solo el ejecutable). El script
se detiene ante cualquier error. La versión del instalador sale de `APP_VERSION` en
`app/utils/constants.py`: **súbela allí antes de cada release**.

Alternativa sin máquina Windows: ejecutar el workflow **Windows build** (pestaña Actions →
*Run workflow*, o subir un tag `v*`). El instalador queda como artefacto `TurnosDesktopSetup`.

### Compilar a mano

```powershell
pip install -r requirements-build.txt
pyinstaller --noconfirm --distpath dist --workpath build packaging\turnos_desktop.spec
iscc /DAppVersion=0.1.0 installer\TurnosDesktop.iss
```

## 4. Qué hace el instalador

- Instala por usuario en `%LOCALAPPDATA%\Programs\TurnosDesktop`, **sin pedir administrador**
  (el asistente permite elegir instalar para todos los usuarios).
- Tarea **"Iniciar Turnos Desktop al iniciar Windows"** (marcada por defecto): escribe
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\TurnosDesktop`. Se elimina al desinstalar.
  Para quitarlo después: Administrador de tareas → Inicio, o reinstalar sin esa casilla.
- Tarea opcional de acceso directo en el escritorio; acceso directo en el menú Inicio.
- Cierra la aplicación en ejecución antes de actualizar. El `AppId` del `.iss` **no debe
  cambiar**: es lo que permite instalar una versión nueva encima de la anterior.
- Idioma del asistente: español.

## 5. Dónde viven los datos

El ejecutable empaquetado **no** guarda nada junto a la aplicación. Los datos van a:

```
%LOCALAPPDATA%\TurnosDesktop\
    database\turnos.db     Turnos, configuración y eventos (SQLite, modo WAL)
    logs\app.log           Log con rotación (5 MB × 5)
```

- Se crean solos en el primer arranque (esquema y migraciones incluidos).
- **Actualizar o desinstalar no los borra**: pueden contener turnos pendientes. Para empezar de
  cero, cerrar la app y borrar esa carpeta a mano.
- `TURNOS_HOME` cambia la carpeta (también en el ejecutable). Se resuelve en
  `constants.resolve_base_dir()`: `TURNOS_HOME` → (empaquetado) `%LOCALAPPDATA%\TurnosDesktop`
  → (desarrollo) raíz del repo.
- El **token del HUB** no está en la base de datos: vive en el Administrador de credenciales de
  Windows (servicio `TurnosDesktop`). No viaja en una copia de la carpeta de datos; en un equipo
  nuevo hay que volver a ingresarlo.

## 6. Prueba de instalación limpia (criterio de la Fase 9)

En una VM o PC de Windows **sin Python**:

1. Ejecutar `TurnosDesktopSetup.exe`. Debe instalar sin errores y abrir la app al terminar.
2. Aparece el icono en la bandeja y la ventana abre en Inicio. Se creó
   `%LOCALAPPDATA%\TurnosDesktop\database\turnos.db`.
3. Configuración: guardar HUB/terminal y un token; cerrar y reabrir → los valores persisten.
4. Hardware → puerto `loop://` → Diagnóstico → *Probar serial* y *Probar impresora* (con la
   impresora de Windows elegida en *Windows Printer*, o la predeterminada).
5. Reiniciar Windows: la app arranca sola (si la tarea quedó marcada).
6. Ejecutar una versión nueva del instalador encima: conserva turnos y configuración.
7. Desinstalar: desaparecen programa, accesos directos y la entrada de inicio; los datos quedan.

Autoverificación sin interfaz (útil para scripts o soporte):

```powershell
$env:TURNOS_HOME = "$env:TEMP\turnos-test"
& "$env:LOCALAPPDATA\Programs\TurnosDesktop\TurnosDesktop.exe" --self-check
$LASTEXITCODE        # 0 = OK; el detalle queda en %TURNOS_HOME%\logs\app.log
```

Comprueba plugins de Qt, construcción de todas las pantallas, base de datos, listado de puertos
seriales y de impresoras, y keyring. El resultado queda en el log (`SELF-CHECK OK` / `failed`)
porque el `.exe` no tiene consola.

## 7. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| SmartScreen: "Windows protegió su PC" | El instalador no está firmado. *Más información → Ejecutar de todas formas*, o firmarlo (§8). |
| El antivirus pone el `.exe` en cuarentena | Falso positivo típico de PyInstaller. Mantener `onedir`, firmar el código y enviar el binario al antivirus como falso positivo. |
| `ModuleNotFoundError` en el `.exe` pero no con `python run.py` | Falta un hidden import: agregarlo a `hidden` en el `.spec` y reconstruir. |
| "No se pudo guardar 'api_token' en el almacén" | Credential Manager no disponible para ese usuario/sesión. Ver `logs\app.log`. |
| La app no abre / se cierra al iniciar | Correr `--self-check` y leer `logs\app.log`. |
| Cerrar la ventana no cierra la app | Es intencional: sigue en la bandeja. Salir con clic derecho → *Salir*. |
| `iscc` no se encuentra | Instalar Inno Setup 6 o agregar su carpeta al `PATH`. |

## 8. Pendiente

- **Probar en Windows limpio** (§6) y registrar el resultado aquí.
- **Firma de código** del `.exe` y del instalador (certificado) para evitar SmartScreen.
- **Icono definitivo** en `resources/icons/app.ico`.
- Editor/nombre de la empresa en `AppPublisher` del `.iss`.
- Cuando existan las Fases 7-8, volver a ejecutar §6 con el HUB y la impresora reales.
- Opcional: casilla en la app para activar/desactivar "iniciar con Windows" sin reinstalar.

# CorreosCogent

CorreosCogent automatiza el procesamiento de notificaciones de abuso enviadas por
Cogent. Consulta una bandeja de Gmail mediante IMAP, localiza los enlaces de los
tickets, valida su destino y, si está habilitado, publica una respuesta y solicita
el cambio de estado del caso. Cada intento queda registrado en un archivo CSV y en
una base de datos SQLite para facilitar su operación y auditoría.

## Características

- Conexión cifrada a Gmail mediante IMAP sobre TLS.
- Apertura de `INBOX` en modo de solo lectura; no marca ni modifica mensajes.
- Filtrado por remitente exacto y por fecha en la zona horaria de Bogotá (UTC-5).
- Extracción de enlaces desde cuerpos de texto y HTML, ignorando adjuntos.
- Deduplicación de un mismo ticket dentro del periodo procesado.
- Validación estricta del protocolo, host, puerto y ruta antes de acceder a Cogent.
- Consulta previa para evitar repetir una respuesta visible o actuar sobre un caso cerrado.
- Modo de simulación que procesa los mensajes sin enviar formularios.
- Historial append-only en SQLite y exportación atómica a CSV.
- Bloqueo local con `flock` para impedir ejecuciones simultáneas.
- Implementación basada únicamente en la biblioteca estándar de Python.

## Flujo de procesamiento

1. `run.sh` carga las variables de `.env`, crea los directorios operativos y
   obtiene un bloqueo exclusivo local.
2. `cogent_email.py` abre `INBOX` en modo de solo lectura y busca mensajes del
   remitente configurado.
3. La búsqueda IMAP se amplía un día a cada lado; después se comprueba la fecha real
   en la zona horaria de Bogotá para evitar omisiones en los límites.
4. Se valida nuevamente el remitente y se extraen enlaces de las partes
   `text/plain` y `text/html` que no sean adjuntos.
5. Los enlaces que representan el mismo ticket se consolidan durante la ejecución.
6. Si el envío está habilitado, se abre el formulario, se obtiene el token CSRF y
   se comprueba el estado y contenido actual del ticket.
7. Si corresponde, se publica la respuesta y se confirma el texto o cambio de estado.
8. El resultado se agrega a SQLite y se escribe en el CSV del periodo.

## Estructura

```text
CorreosCogent/
├── .env.example             # Plantilla de configuración
├── .gitignore               # Exclusiones de credenciales y datos operativos
├── cogent_email.py          # Aplicación principal
├── crontab.example          # Ejemplo de programación periódica
├── run.sh                   # Carga del entorno y bloqueo de concurrencia
├── tests/
│   └── test_cogent_email.py # Pruebas unitarias
├── logs/                    # Logs de cron; se crea al ejecutar
├── output/                  # Informes CSV; se crea al ejecutar
└── state/                   # SQLite y bloqueo; se crea al ejecutar
```

`logs/`, `output/`, `state/` y `.env` están excluidos del control de versiones.

## Requisitos

- Linux con `/usr/bin/python3` y `/usr/bin/flock`.
- Python 3.8 o superior; no requiere paquetes de `pip`.
- Acceso saliente a `imap.gmail.com:993` y
  `https://abuse.sys.cogentco.com:443`.
- Una cuenta de Gmail o Google Workspace que reciba las notificaciones.
- Una contraseña de aplicación válida para esa cuenta.
- Permisos de escritura en el directorio del proyecto.

## Instalación y configuración

```bash
cd /ruta/a/CorreosCogent
cp .env.example .env
chmod 600 .env
chmod 750 run.sh cogent_email.py
```

Edita `.env`:

```dotenv
GMAIL_USER=cuenta@dominio.com
GMAIL_APP_PASSWORD=CONTRASENA_DE_APLICACION
COGENT_SENDER=abuse@cogentco.com
COGENT_POST_ENABLED=true
COGENT_REPLY_TEXT="Hello, already resolved and blocked the client."
COGENT_CHANGE_STATUS=RESOLVED
```

| Variable | Obligatoria | Predeterminado | Descripción |
|---|---:|---|---|
| `GMAIL_USER` | Sí | — | Cuenta que recibe las notificaciones. |
| `GMAIL_APP_PASSWORD` | Sí | — | Contraseña de aplicación. Sus espacios se eliminan al autenticar. |
| `COGENT_SENDER` | No | `abuse@cogentco.com` | Dirección exacta admitida en `From`. |
| `COGENT_POST_ENABLED` | No | `true` | Habilita el envío con `1`, `true`, `yes`, `si` o `sí`. |
| `COGENT_REPLY_TEXT` | No | `Hello, already resolved and blocked the client.` | Respuesta publicada; no puede estar vacía si el envío está activo. |
| `COGENT_CHANGE_STATUS` | No | `RESOLVED` | Solo acepta `RESOLVED` u `OPEN`. |

`run.sh` crea los directorios con permisos restrictivos. También pueden prepararse:

```bash
mkdir -p logs output state
chmod 700 state
chmod 750 logs output
```

## Uso

```bash
./run.sh                         # Procesa el día anterior
./run.sh --today                 # Procesa el día actual
./run.sh --date 2026-08-25       # Procesa una fecha concreta
./run.sh --month 2026-08         # Procesa un mes completo
./run.sh --cron                  # Ejecuta la lógica periódica
./run.sh --today --no-post       # Simula sin enviar respuestas
./run.sh --today --stdout        # Emite el CSV por stdout
```

`--date`, `--month`, `--today` y `--cron` son mutuamente excluyentes. Sin
ninguna de ellas se procesa el día anterior.

### Primera ejecución segura

```bash
./run.sh --today --no-post
```

Este modo crea el CSV y agrega filas `OMITIDO` a SQLite, pero no publica
formularios. Tras revisar el resultado, prueba un envío real con:

```bash
./run.sh --today
```

### Ejecución periódica

Con `--cron` se procesa el día actual. Entre las 00:00 y las 00:29 también se
procesa el día anterior para cubrir mensajes cercanos a medianoche.

Adapta las rutas absolutas de `crontab.example` a la instalación:

```cron
CRON_TZ=America/Bogota
*/30 * * * * /ruta/a/CorreosCogent/run.sh --cron >> /ruta/a/CorreosCogent/logs/cron.log 2>&1
```

Instala la entrada con `crontab -e` y compruébala con `crontab -l`. El archivo
`state/cron.lock` coordina procesos de la misma instalación, pero no copias en
otros directorios o servidores. Evita más de una instancia sobre el mismo buzón.

## Estados y códigos de salida

| Estado | Significado |
|---|---|
| `ENVIADO` | Cogent confirmó la respuesta o el cambio solicitado. |
| `YA_EXISTIA` | El texto configurado ya estaba visible en el ticket. |
| `YA_RESUELTO` | El ticket ya aparecía como resuelto o cerrado. |
| `OMITIDO` | El envío estaba deshabilitado o se usó `--no-post`. |
| `ERROR` | Falló la validación, red, HTTP o confirmación. |

- `0`: ejecución sin fallos, o ronda omitida por un bloqueo local activo.
- `1`: error operativo, IMAP, autenticación, SQLite o envío no confirmado.
- `2`: argumentos o configuración inválidos.

## Informes CSV

Los informes se guardan como `output/AAAA-MM-DD.csv` para días y
`output/AAAA-MM.csv` para meses. La escritura es atómica y repetir el periodo
reemplaza su CSV. Con `--stdout` no se crea el archivo, pero SQLite sí se actualiza.

| Columna | Contenido |
|---|---|
| `fecha_objetivo` | Día del mensaje en la zona horaria de Bogotá. |
| `uid` | UID asignado por Gmail. |
| `message_id` | Encabezado `Message-ID`. |
| `recibido` | Fecha y hora normalizada con zona horaria. |
| `remitente` | Remitente validado. |
| `asunto` | Asunto del mensaje. |
| `url` | Enlace del ticket. |
| `post_estado` | Resultado funcional. |
| `post_http` | Código HTTP, cuando exista. |
| `post_resultado` | Detalle del resultado o error. |
| `post_fecha` | Fecha y hora del intento. |

## Historial SQLite

`state/cogent_tracking.sqlite3` contiene la tabla `cogent_tracking`, con una fila
por ticket procesado: identificador y fecha de registro, periodo, UID,
`Message-ID`, recepción, clave y URL del ticket, estado, éxito, HTTP, detalle y
fecha del intento.

El historial es append-only: no tiene una restricción única ni se consulta para
decidir si un caso debe procesarse. La deduplicación se realiza dentro del periodo y
la prevención de reenvíos mediante el contenido remoto. Reprocesar agrega filas.

```bash
sqlite3 state/cogent_tracking.sqlite3 \
  "SELECT id, recorded_at, post_estado, url FROM cogent_tracking ORDER BY id DESC LIMIT 20;"

sqlite3 state/cogent_tracking.sqlite3 \
  "SELECT ticket_key, COUNT(*) FROM cogent_tracking GROUP BY ticket_key ORDER BY COUNT(*) DESC;"

sqlite3 state/cogent_tracking.sqlite3 \
  "SELECT post_estado, COUNT(*) FROM cogent_tracking GROUP BY post_estado;"
```

Eliminar la base borra el historial local, no Gmail ni los tickets remotos. La tabla
se crea de nuevo en la siguiente ejecución.

## Seguridad

- No publiques `.env`; usa una contraseña de aplicación dedicada y rótala si se expone.
- Solo se aceptan URLs HTTPS de `abuse.sys.cogentco.com:443` con rutas
  `/ash/collect/<numero>/<token>`.
- Las respuestas HTTP se limitan a 2 MiB y la red tiene un timeout de 30 segundos.
- Las cookies y el token CSRF se manejan por cada operación.
- Gmail se abre en modo de solo lectura.
- `umask 077` restringe credenciales, SQLite, CSV y bloqueo al usuario ejecutor.
- Respalda SQLite si el historial tiene valor de auditoría.

## Diagnóstico

```bash
tail -n 100 logs/cron.log
pgrep -af 'CorreosCogent/cogent_email.py'
ls -l state/cron.lock
```

- **Falta `.env`:** copia `.env.example`, configura credenciales y aplica `600`.
- **Gmail rechaza el acceso:** revisa usuario, contraseña de aplicación, IMAP y las
  políticas de Google Workspace.
- **No aparecen mensajes:** confirma remitente, fecha e `INBOX`; el filtro final usa
  la hora de Bogotá.
- **La ronda se omite:** revisa el proceso que conserva `state/cron.lock`. No hace
  falta borrar el archivo si ningún proceso mantiene abierto su descriptor.
- **Estado `ERROR`:** consulta `post_http` y `post_resultado`; valida conectividad,
  certificado, formato del enlace y respuesta de Cogent.
- **El caso se repite en SQLite:** es esperado al reprocesar; SQLite es un historial,
  no una llave de idempotencia.

## Limitaciones

- IMAP está fijado a Gmail (`imap.gmail.com:993`).
- La zona horaria está fijada a `America/Bogota` (UTC-5).
- Solo se inspecciona `INBOX`.
- El formulario admite `OPEN` y `RESOLVED`.
- El bloqueo solo evita concurrencia dentro de la misma instalación.
- Cambios en el HTML de Cogent pueden requerir actualizar analizadores y validaciones.

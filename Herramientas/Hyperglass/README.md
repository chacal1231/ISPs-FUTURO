# Looking Glass con Hyperglass 1.0.4 y Arista EOS

Guía de referencia para desplegar un Looking Glass con consultas BGP, ping y traceroute IPv4/IPv6, branding propio y validación RPKI externa.

Todos los nombres, ASN, direcciones y secretos de los ejemplos son ficticios. Las direcciones `192.0.2.0/24` y `2001:db8::/32` son de documentación: deben reemplazarse para realizar consultas reales.

## 1. Alcance y requisitos

Esta guía corresponde específicamente a **Hyperglass 1.0.4**. No utiliza el esquema de Hyperglass 2.x.

Entorno de referencia:

- Linux con systemd.
- Python 3.8 y virtualenv.
- Node.js 14.21.3 y Yarn Classic.
- Redis en `127.0.0.1:6379`.
- Router Arista EOS/vEOS accesible por SSH.
- Salida HTTPS para las consultas RPKI externas y las dependencias del frontend.

Es una pila heredada: estas versiones no constituyen una recomendación para un despliegue nuevo. La instalación de dependencias antiguas puede requerir ajustes según la distribución y las versiones de sus herramientas.

Rutas de ejemplo:

| Contenido | Ruta |
| --- | --- |
| Código fuente | `/opt/hyperglass/app` |
| Virtualenv | `/opt/hyperglass/venv` |
| Configuración | `/etc/hyperglass` |
| Frontend publicado | `/etc/hyperglass/static/ui` |
| Imágenes publicadas | `/etc/hyperglass/static/images` |

## 2. Instalación de referencia

Con Python 3.8, Node.js y Yarn ya instalados, ejecuta como administrador:

```bash
apt-get update
apt-get install -y git redis-server build-essential python3.8-dev python3.8-venv
systemctl enable --now redis-server

mkdir -p /opt/hyperglass /etc/hyperglass
git clone --branch v1.0.4 --depth 1 https://github.com/thatmattlove/hyperglass.git /opt/hyperglass/app
python3.8 -m venv /opt/hyperglass/venv
source /opt/hyperglass/venv/bin/activate
python -m pip install /opt/hyperglass/app
python -m pip show hyperglass

node --version
yarn --version
redis-cli ping
```

El paquete instalado debe indicar `1.0.4`; Redis debe responder `PONG`. Los nombres de paquetes del sistema pueden variar por distribución. Este procedimiento describe una instalación de referencia, no un instalador probado en todas las distribuciones.

No crees simultáneamente `/etc/hyperglass` y un directorio `hyperglass` dentro del home del usuario que ejecuta la aplicación: esta versión puede rechazar esa ambigüedad al buscar su configuración.

## 3. Configuración principal

Crea `/etc/hyperglass/hyperglass.yaml`:

```yaml
org_name: Red de ejemplo
site_title: Looking Glass
site_description: Consultas de enrutamiento
primary_asn: 64512

listen_address: 0.0.0.0
listen_port: 8001
debug: false

structured:
  rpki:
    mode: external

web:
  links:
    - title: PeeringDB
      url: https://www.peeringdb.com/asn/64512
  text:
    title_mode: text_only
    title: Looking Glass
    subtitle: Red de ejemplo
```

Sustituye el ASN privado de ejemplo por tu ASN público para que el enlace de PeeringDB apunte a tu red.

`logo`, `links` y `text` pertenecen a `web`. Poner `logo` o `text` en la raíz produce `extra fields not permitted`. El título y el subtítulo admiten hasta 32 caracteres en esta versión.

## 4. Router Arista y restricciones de consulta

Crea `/etc/hyperglass/devices.yaml`. La raíz correcta en 1.0.4 es **`routers:`**:

```yaml
routers:
  - name: pop-ejemplo
    display_name: POP de ejemplo
    address: 192.0.2.10
    port: 22
    network:
      name: red-ejemplo
      display_name: Red de ejemplo
    credential:
      username: lookingglass
      password: "REEMPLAZAR_LOCALMENTE"
    nos: arista_eos
    vrfs:
      - name: global
        display_name: Global
        default: true
        ipv4:
          source_address: 192.0.2.10
          access_list:
            - network: 10.0.0.0/8
              action: deny
              ge: 8
              le: 32
            - network: 172.16.0.0/12
              action: deny
              ge: 12
              le: 32
            - network: 192.168.0.0/16
              action: deny
              ge: 16
              le: 32
            - network: 0.0.0.0/0
              action: permit
              ge: 0
              le: 32
        ipv6:
          source_address: 2001:db8::10
          access_list:
            - network: fc00::/7
              action: deny
              ge: 7
              le: 128
            - network: fe80::/10
              action: deny
              ge: 10
              le: 128
            - network: ::/0
              action: permit
              ge: 0
              le: 128
```

La dirección `address` se usa para SSH. Las direcciones `source_address` se usan como origen de ping y traceroute y deben existir en el router; pueden ser distintas de la dirección SSH.

Las reglas `deny` deben aparecer antes del permiso general. Este ejemplo bloquea RFC1918, ULA y link-local IPv6; no es una lista completa de rangos especiales. Si corresponde a tu política, añade también CGNAT `100.64.0.0/10`, loopback y link-local IPv4.

Estas restricciones filtran destinos de consulta. No ocultan direcciones internas incluidas en las respuestas de BGP o en los saltos de traceroute.

El valor `REEMPLAZAR_LOCALMENTE` es un marcador literal, no una variable de entorno. Escribe el secreto únicamente en el servidor y restringe la lectura del archivo al usuario del servicio.

## 5. Privilegios SSH en EOS

Prueba con el mismo usuario que utilizará Hyperglass:

```bash
ssh lookingglass@192.0.2.10
```

Dentro de EOS, usando una dirección de origen real:

```text
show users accounts
ping ip 1.1.1.1 source 192.0.2.10
```

En algunas versiones el comando de usuarios se llama `show user-account`. Si el ping devuelve `privileged mode required`, comprueba si funciona después de ejecutar `enable`.

El controlador Netmiko de Hyperglass 1.0.4 no ejecuta `enable` antes de las consultas. Para un entorno con usuarios locales, el ingreso directo a modo privilegiado puede configurarse así, sobre un usuario ya creado:

```text
configure terminal
username lookingglass privilege 15
aaa authorization exec default local
end
```

La autorización EXEC es una configuración global: revisa la política existente antes de aplicarla si utilizas TACACS+ o RADIUS. Conserva la sesión actual y prueba otra conexión SSH; debe abrir directamente en el prompt `#`. Guarda con `write memory` después de verificar el acceso y las consultas.

El nivel de privilegio y el rol son controles distintos. Usa una cuenta dedicada y un rol que permita los comandos de consulta necesarios; esta guía no define una política completa de solo lectura.

## 6. Logo y PeeringDB

Guarda tu imagen en `/etc/hyperglass/logo.png` y añade al bloque `web` existente:

```yaml
  logo:
    light: /etc/hyperglass/logo.png
    dark: /etc/hyperglass/logo.png
    width: 280
```

Cambia `web.text.title_mode` a `logo_subtitle` para mostrar el logo y el subtítulo. Puedes usar archivos distintos para ambos temas. Los archivos deben existir antes de arrancar.

Para forzar la compilación después de modificar el branding:

```bash
source /opt/hyperglass/venv/bin/activate
export NODE_OPTIONS="--max-old-space-size=4096"
hyperglass build-ui
```

Si reemplazas una imagen conservando su nombre, Hyperglass puede saltarse la compilación porque el identificador del build depende de la configuración. Para un logo PNG que ya se servía como PNG, también puedes actualizar únicamente las copias publicadas:

```bash
cp /etc/hyperglass/logo.png /etc/hyperglass/static/images/light.png
cp /etc/hyperglass/logo.png /etc/hyperglass/static/images/dark.png
```

Después recarga el navegador con Ctrl+F5. Si cambias el formato o las opciones visuales, recompila el frontend.

## 7. RPKI externo

La opción `structured.rpki.mode: external` usa la API HTTPS de Cloudflare integrada en 1.0.4. No configura una sesión RPKI-RTR con el router ni permite seleccionar una URL arbitraria mediante YAML.

La validación compara el prefijo BGP y el ASN de origen del `AS_PATH`. Arista tiene salida estructurada automática: omite `structured_output` en el dispositivo. En el código revisado de 1.0.4, establecerlo explícitamente en `true` puede desactivarlo por un defecto de su validador.

Los estados incluyen válido, inválido, sin ROA y no verificado. Una ruta sin AS de origen o un fallo del servicio externo puede aparecer como no verificada. La disponibilidad de esta API externa debe comprobarse en cada despliegue:

```bash
curl --max-time 20 -sS https://rpki.cloudflare.com/api/graphql \
  -H 'Content-Type: application/json' \
  --data '{"query":"query GetValidation { validation(prefix: \"1.1.1.0/24\", asn: 13335) { state } }"}'
```

RPKI se muestra en las consultas BGP estructuradas, no en ping o traceroute. No modifica las políticas BGP del router.

## 8. Primer arranque y diagnóstico

```bash
source /opt/hyperglass/venv/bin/activate
export NODE_OPTIONS="--max-old-space-size=4096"
hyperglass start
```

Mantén esa terminal abierta. Desde otra sesión:

```bash
curl http://127.0.0.1:8001/api/info
curl http://127.0.0.1:8001/api/devices
curl http://127.0.0.1:8001/api/queries
ss -lntp 'sport = :8001'
```

Verifica desde la web ping, traceroute y rutas BGP en ambas familias. Los resultados anteriores pueden estar en Redis; reiniciar Hyperglass no garantiza borrar esa caché.

## 9. Servicio systemd

Localiza primero Node y Yarn en la terminal donde funciona el arranque manual:

```bash
command -v node
command -v yarn
```

El ejemplo siguiente supone que ambos están en `/usr/local/bin`. Si están instalados mediante NVM, añade su directorio real al `PATH` del servicio. systemd no carga automáticamente el entorno NVM de tu terminal.

Crea `/etc/systemd/system/hyperglass.service`:

```ini
[Unit]
Description=Hyperglass Looking Glass
Wants=network-online.target
After=network-online.target redis-server.service
Requires=redis-server.service
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=/etc/hyperglass
Environment="PATH=/opt/hyperglass/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NODE_OPTIONS=--max-old-space-size=4096"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/hyperglass/venv/bin/hyperglass start
Restart=on-failure
RestartSec=10
KillSignal=SIGTERM
KillMode=mixed
TimeoutStopSec=60
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hyperglass

[Install]
WantedBy=multi-user.target
```

Este ejemplo reproduce una ejecución como administrador. Para una cuenta de servicio dedicada, adapta los permisos de configuración, código, imágenes y compilación, y verifica que no haya ambigüedad entre los directorios de configuración.

Detén primero la instancia manual con Ctrl+C o enviando SIGTERM a su PID principal. Espera a que el puerto 8001 quede libre y activa systemd:

```bash
sudo systemd-analyze verify /etc/systemd/system/hyperglass.service
sudo systemctl daemon-reload
sudo systemctl enable --now hyperglass
sudo systemctl status hyperglass --no-pager
```

Operación habitual:

```bash
sudo systemctl restart hyperglass
sudo systemctl stop hyperglass
sudo journalctl -u hyperglass -f
```

Si el servicio alcanzó el límite de intentos, corrige la causa y ejecuta:

```bash
sudo systemctl reset-failed hyperglass
sudo systemctl restart hyperglass
```

## 10. Problemas frecuentes

| Síntoma | Comprobación o solución |
| --- | --- |
| `Unable to build network to device mapping` | Usar `routers:` como raíz de `devices.yaml`. |
| Node sin memoria | Configurar `NODE_OPTIONS=--max-old-space-size=4096`. |
| La API responde pero `/` devuelve `Not Found` | Verificar `static/ui/index.html` y ejecutar `hyperglass build-ui`. |
| `extra fields not permitted` en logo/text | Colocar ambos dentro de `web`. |
| Logo anterior | Actualizar las imágenes publicadas o forzar build; recargar el navegador. |
| `privileged mode required` | Verificar que una nueva sesión SSH entre en `#` y tenga el rol adecuado. |
| `TypeError` en `get_node_version` | Node no está en el `PATH` del servicio. |
| Puerto 8001 ocupado | Detener la instancia manual antes de iniciar systemd. |
| Mensaje de interrupción de teclado | Ctrl+C detiene el proceso en primer plano. |
| RPKI no verificado | Comprobar salida estructurada, AS_PATH, acceso HTTPS y respuesta de la API externa. |

## 11. Publicación del tutorial sin secretos

Publica este README desde un directorio nuevo. No inicialices el repositorio sobre la configuración operativa ni copies logs, credenciales, claves, archivos temporales o el frontend compilado: estos pueden contener datos de la instalación.

```bash
mkdir -p ~/hyperglass-tutorial
cp /etc/hyperglass/README.md ~/hyperglass-tutorial/README.md
cd ~/hyperglass-tutorial
git init
git add README.md
git diff --cached
git commit -m "Documentar despliegue de Hyperglass 1.0.4"
```

Después de revisar el contenido, añade el remoto de tu repositorio y publica:

```bash
git branch -M main
git remote add origin URL_DE_TU_REPOSITORIO
git push -u origin main
```

Si añades ejemplos YAML, conserva únicamente valores ficticios. No publiques salidas de depuración: algunas registran la configuración del dispositivo con credenciales. Quitar un secreto de la última versión de un archivo no lo elimina del historial Git.

## Referencias

- [Código de Hyperglass v1.0.4](https://github.com/thatmattlove/hyperglass/tree/v1.0.4).
- [Esquema de branding](https://github.com/thatmattlove/hyperglass/blob/v1.0.4/hyperglass/models/config/web.py).
- [Listas de acceso y VRF](https://github.com/thatmattlove/hyperglass/blob/v1.0.4/hyperglass/models/config/vrf.py).
- [Integración RPKI externa](https://github.com/thatmattlove/hyperglass/blob/v1.0.4/hyperglass/external/rpki.py).
- [Seguridad de usuarios en Arista EOS](https://www.arista.com/en/um-eos/eos-user-security).
- [Rangos especiales IPv4 de IANA](https://www.iana.org/assignments/iana-ipv4-special-registry).
- [Rangos especiales IPv6 de IANA](https://www.iana.org/assignments/iana-ipv6-special-registry).

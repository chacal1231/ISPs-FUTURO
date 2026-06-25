# Instalación de GenieACS 1.2.7 en Ubuntu 20.04

Guía paso a paso para instalar GenieACS en Ubuntu 20.04 usando Node.js, MongoDB, npm y servicios `systemd`.

## 1. Actualizar el sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg ca-certificates build-essential
```

## 2. Instalar Node.js

> Nota: Node.js 18 muestra advertencia de deprecación en NodeSource. Para Ubuntu 20.04 se recomienda usar Node.js 20 LTS.

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Validar instalación:

```bash
node -v
npm -v
```

## 3. Instalar MongoDB

Instalar dependencias:

```bash
sudo apt install -y gnupg curl
```

Agregar llave de MongoDB:

```bash
curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
```

Agregar repositorio para Ubuntu 20.04 Focal:

```bash
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | \
sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
```

Instalar MongoDB:

```bash
sudo apt update
sudo apt install -y mongodb-org
```

Habilitar y arrancar MongoDB:

```bash
sudo systemctl enable mongod
sudo systemctl start mongod
sudo systemctl status mongod
```

## 4. Instalar GenieACS

Instalar GenieACS 1.2.7:

```bash
sudo npm install -g --unsafe-perm genieacs@1.2.7
```

Resultado esperado:

```text
added 130 packages in 3s
```

> El aviso de nueva versión de npm no es un error. No es necesario actualizar npm en este momento.

Validar binarios:

```bash
which genieacs-cwmp
which genieacs-nbi
which genieacs-fs
which genieacs-ui
```

Rutas esperadas:

```text
/usr/bin/genieacs-cwmp
/usr/bin/genieacs-nbi
/usr/bin/genieacs-fs
/usr/bin/genieacs-ui
```

## 5. Crear usuario y directorios

```bash
sudo useradd --system --no-create-home --user-group genieacs

sudo mkdir -p /opt/genieacs/ext
sudo mkdir -p /var/log/genieacs

sudo chown -R genieacs:genieacs /opt/genieacs
sudo chown -R genieacs:genieacs /var/log/genieacs
```

## 6. Crear archivo de variables de entorno

Crear archivo:

```bash
sudo nano /opt/genieacs/genieacs.env
```

Contenido inicial:

```bash
GENIEACS_CWMP_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-cwmp-access.log
GENIEACS_NBI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-nbi-access.log
GENIEACS_FS_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-fs-access.log
GENIEACS_UI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-ui-access.log
GENIEACS_DEBUG_FILE=/var/log/genieacs/genieacs-debug.yaml
NODE_OPTIONS=--enable-source-maps
GENIEACS_EXT_DIR=/opt/genieacs/ext
```

Generar secreto JWT:

```bash
node -e "console.log('GENIEACS_UI_JWT_SECRET=' + require('crypto').randomBytes(128).toString('hex'))" | sudo tee -a /opt/genieacs/genieacs.env
```

Agregar puertos e interfaces explícitos al final del archivo:

```bash
GENIEACS_CWMP_INTERFACE=0.0.0.0
GENIEACS_CWMP_PORT=7547

GENIEACS_NBI_INTERFACE=0.0.0.0
GENIEACS_NBI_PORT=7557

GENIEACS_FS_INTERFACE=0.0.0.0
GENIEACS_FS_PORT=7567

GENIEACS_UI_INTERFACE=0.0.0.0
GENIEACS_UI_PORT=3000
```

Aplicar permisos:

```bash
sudo chown genieacs:genieacs /opt/genieacs/genieacs.env
sudo chmod 600 /opt/genieacs/genieacs.env
```

## 7. Crear servicios systemd

### 7.1 Servicio CWMP

```bash
sudo nano /etc/systemd/system/genieacs-cwmp.service
```

Contenido:

```ini
[Unit]
Description=GenieACS CWMP
After=network.target mongod.service

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-cwmp
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7.2 Servicio NBI

```bash
sudo nano /etc/systemd/system/genieacs-nbi.service
```

Contenido:

```ini
[Unit]
Description=GenieACS NBI
After=network.target mongod.service

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-nbi
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7.3 Servicio FS

```bash
sudo nano /etc/systemd/system/genieacs-fs.service
```

Contenido:

```ini
[Unit]
Description=GenieACS FS
After=network.target mongod.service

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-fs
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7.4 Servicio UI

```bash
sudo nano /etc/systemd/system/genieacs-ui.service
```

Contenido:

```ini
[Unit]
Description=GenieACS UI
After=network.target mongod.service

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-ui
Restart=always

[Install]
WantedBy=multi-user.target
```

## 8. Activar y arrancar servicios

```bash
sudo systemctl daemon-reload

sudo systemctl enable genieacs-cwmp genieacs-nbi genieacs-fs genieacs-ui

sudo systemctl start genieacs-cwmp genieacs-nbi genieacs-fs genieacs-ui
```

Validar estado:

```bash
sudo systemctl status genieacs-cwmp
sudo systemctl status genieacs-nbi
sudo systemctl status genieacs-fs
sudo systemctl status genieacs-ui
```

Estado esperado:

```text
Active: active (running)
```

## 9. Validar puertos

```bash
sudo ss -ltnp | grep -E '3000|7547|7557|7567'
```

Puertos esperados:

```text
3000  GenieACS UI
7547  CWMP / TR-069
7557  NBI API
7567  File Server
```

Probar localmente:

```bash
curl -I http://127.0.0.1:3000
curl http://127.0.0.1:7557/devices
```

## 10. Acceso a GenieACS

Interfaz web:

```text
http://IP_DEL_SERVIDOR:3000
```

ACS URL para CPE/ONT/router:

```text
http://IP_DEL_SERVIDOR:7547/
```

## 11. Firewall

Si usas UFW:

```bash
sudo ufw allow 3000/tcp
sudo ufw allow 7547/tcp
sudo ufw allow 7557/tcp
sudo ufw allow 7567/tcp
sudo ufw reload
```

Recomendación para producción:

```text
7547 CWMP: permitir solo desde redes de CPE/clientes.
3000 UI: proteger con Nginx + HTTPS + firewall.
7557 NBI: dejar solo para localhost o red administrativa.
7567 FS: abrir solo si se usará para firmware/configs.
```

## 12. Logs y diagnóstico

Ver logs de cada servicio:

```bash
journalctl -u genieacs-cwmp -n 100 --no-pager
journalctl -u genieacs-nbi -n 100 --no-pager
journalctl -u genieacs-fs -n 100 --no-pager
journalctl -u genieacs-ui -n 100 --no-pager
```

Logs en vivo:

```bash
journalctl -u genieacs-cwmp -f
journalctl -u genieacs-ui -f
```

Validar procesos:

```bash
ps aux | grep genieacs
```

Validar MongoDB:

```bash
sudo systemctl status mongod
```

## 13. Problema común: servicios activos pero puertos no aparecen

Si los servicios aparecen como:

```text
Active: active (running)
```

pero este comando no muestra nada:

```bash
sudo ss -tulpn | grep -E '3000|7547|7557|7567'
```

revisa que `/opt/genieacs/genieacs.env` tenga las variables explícitas:

```bash
GENIEACS_CWMP_INTERFACE=0.0.0.0
GENIEACS_CWMP_PORT=7547

GENIEACS_NBI_INTERFACE=0.0.0.0
GENIEACS_NBI_PORT=7557

GENIEACS_FS_INTERFACE=0.0.0.0
GENIEACS_FS_PORT=7567

GENIEACS_UI_INTERFACE=0.0.0.0
GENIEACS_UI_PORT=3000
```

Luego reinicia:

```bash
sudo systemctl daemon-reload
sudo systemctl restart genieacs-cwmp genieacs-nbi genieacs-fs genieacs-ui
```

Y vuelve a validar:

```bash
sudo ss -ltnp | grep -E '3000|7547|7557|7567'
```
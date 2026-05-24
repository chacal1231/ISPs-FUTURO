# 📡 NOC DOCUMENTACIÓN OFICIAL
# Instalación y Puesta en Producción de Asterisk 23 (Compilado desde Source)

---

## 🎯 Objetivo
Documentar el procedimiento estándar para instalación, compilación y configuración inicial de **Asterisk 23** en servidores Ubuntu/Debian dentro del entorno NOC.

Este procedimiento aplica para:
- Nuevas instalaciones
- Reinstalaciones controladas
- Migraciones de versión

---

# 1️⃣ Preparación del Sistema

## 🔄 Actualización del servidor
```bash
apt update -y
apt dist-upgrade -y
```

## ⛔ Deshabilitar servicios innecesarios (optimización servidor PBX)
```bash
systemctl disable systemd-networkd-wait-online.service
systemctl mask systemd-networkd-wait-online.service

systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

reboot
```

---

# 2️⃣ Instalación de Dependencias

```bash
apt install -y wget build-essential subversion acl ffmpeg
```

---

# 3️⃣ Descarga y Compilación de Asterisk

## 📥 Descargar código fuente
```bash
cd /usr/src/

wget http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-23-current.tar.gz
tar zxf asterisk-23-current.tar.gz

cd asterisk-23.*/
```

## 🎵 Habilitar soporte MP3
```bash
contrib/scripts/get_mp3_source.sh
```

## 🧩 Instalar prerequisitos adicionales
```bash
contrib/scripts/install_prereq install
```

## ⚙️ Configuración del entorno de compilación
```bash
./configure
```

## 🛠️ Selección de módulos
```bash
make menuselect
```

Activar:
- Add-ons → `format_mp3`

## 🚀 Compilación optimizada (8 hilos)
```bash
make -j8
```

## 📦 Instalación
```bash
make install
make samples
make config
ldconfig
```

---

# 4️⃣ Seguridad y Usuario de Servicio

## 👤 Crear usuario y grupo dedicado
```bash
addgroup --quiet --system asterisk
adduser --quiet --system --ingroup asterisk --no-create-home --disabled-password asterisk
```

## ⚙️ Configurar servicio para correr como usuario dedicado

Editar:
```bash
nano /etc/default/asterisk
```

Agregar al final:
```bash
AST_USER="asterisk"
AST_GROUP="asterisk"
```

---

# 5️⃣ Permisos y Seguridad de Archivos

```bash
usermod -a -G dialout,audio asterisk

chown -R asterisk: /var/{lib,log,run,spool}/asterisk /usr/lib/asterisk /etc/asterisk
chmod -R 750 /var/{lib,log,run,spool}/asterisk /usr/lib/asterisk /etc/asterisk

setfacl -R -m u:pbx:rwx /etc/asterisk
setfacl -R -m d:u:pbx:rwx /etc/asterisk
```

---

# 6️⃣ Habilitación y Arranque del Servicio

```bash
systemctl enable asterisk
systemctl start asterisk
```

Verificar estado:
```bash
systemctl status asterisk
asterisk -rvvv
```

---

# 7️⃣ Gestión de Audios IVR

## 📂 Crear estructura para MP3
```bash
mkdir -p /var/lib/asterisk/sounds/en/mp3
```

## 📥 Copiar audios
```bash
cp *.mp3 /var/lib/asterisk/sounds/en/mp3
```

## 🔄 Conversión a formato compatible Asterisk (WAV 8kHz mono s16)
```bash
ffmpeg -i AgentesOcupados.mp3 -ar 8000 -ac 1 -sample_fmt s16 AgentesOcupados.wav
```

---

# 📞 Texto Oficial IVR

```
Gracias por llamar a TEVE Y MAS S.A.S.

Para continuar, elija una opción:
Marque uno para Soporte Técnico.
Marque dos para Cartera y Pagos.
Marque tres para Información sobre Nuevos Servicios.

Para escuchar este menú nuevamente, marque cero.
```

---

# ✅ Checklist Post-Instalación (NOC)

- [ ] Servicio activo y habilitado al arranque
- [ ] Usuario asterisk configurado correctamente
- [ ] Permisos verificados
- [ ] Módulo MP3 cargado
- [ ] Audios convertidos correctamente
- [ ] Prueba de llamada interna exitosa
- [ ] Registro SIP funcional

Verificación módulo:
```bash
module show like mp3
```

---

# 🔐 Recomendaciones NOC

- No ejecutar Asterisk como root
- Restringir acceso SSH
- Implementar firewall (ufw / iptables)
- Configurar fail2ban para SIP
- Monitoreo vía Zabbix / Prometheus
- Backup periódico de /etc/asterisk

---

# 📌 Versión Documento
v1.0 – Procedimiento estándar NOC

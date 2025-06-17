# 📘 Guía de instalación de PHPIPAM en Ubuntu

Esta guía te permitirá instalar y configurar PHPIPAM utilizando MariaDB y Apache en un servidor Ubuntu.

---

## 🔧 Requisitos previos

- Ubuntu Server (recomendado 20.04 o superior)
- Acceso como usuario con privilegios `sudo`

---

## 1. Actualizar el sistema

```bash
sudo apt update
sudo apt dist-upgrade
```

---

## 2. Instalar y configurar MariaDB

```bash
sudo apt install mariadb-server mariadb-client
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql_secure_installation
```

> Durante la instalación segura de MariaDB, define una contraseña **segura** y no la olvides.

---

## 3. Crear la base de datos y el usuario

```bash
sudo mysql -u root -p
```

Dentro del prompt de MySQL:

```sql
CREATE DATABASE phpipam;
GRANT ALL ON phpipam.* TO phpipam@localhost IDENTIFIED BY 'StrongDBPassword';
FLUSH PRIVILEGES;
QUIT;
```

---

## 4. Clonar el repositorio PHPIPAM

```bash
sudo git clone --recursive https://github.com/phpipam/phpipam.git /var/www/html/
cd /var/www/html/
sudo cp config.dist.php config.php
```

---

## 5. Editar `config.php`

Edita el archivo `config.php` y define los datos de conexión a la base de datos:

```php
/*** database connection details ******************************/
$db['host'] = 'localhost';
$db['user'] = 'phpipam';
$db['pass'] = 'StrongDBPassword';
$db['name'] = 'phpipam';
$db['port'] = 3306;
```

---

## 6. Instalar y configurar Apache

```bash
sudo apt -y install apache2
sudo a2dissite 000-default.conf
sudo a2enmod rewrite
sudo systemctl restart apache2
```

---

## 7. Instalar módulos PHP requeridos

```bash
sudo apt -y install libapache2-mod-php php-curl php-xmlrpc php-intl php-gd php-gmp php-mysql php-mbstring php-xml php-pear
```

---

## 8. Configurar el VirtualHost

```bash
sudo nano /etc/apache2/sites-available/phpipam.conf
```

Contenido del archivo:

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    DocumentRoot "/var/www/html"
    ServerName ipam.example.com
    ServerAlias www.ipam.example.com

    <Directory "/var/www/html/">
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog "/var/log/apache2/phpipam-error_log"
    CustomLog "/var/log/apache2/phpipam-access_log" combined
</VirtualHost>
```

---

## 9. Cambiar permisos y habilitar sitio

```bash
sudo chown -R www-data:www-data /var/www/html
sudo a2ensite phpipam
sudo systemctl restart apache2
```

---

## 10. Crear tareas cron

```bash
sudo crontab -e
```

Agregar las siguientes líneas:

```cron
*/15 * * * * /usr/bin/php /var/www/html/functions/scripts/pingCheck.php
*/15 * * * * /usr/bin/php /var/www/html/functions/scripts/discoveryCheck.php
```

---

## 11. Importar la base de datos inicial

```bash
sudo mysql -u root -p phpipam < /var/www/html/db/SCHEMA.sql
```

---

## Finalizar instalación

Abre tu navegador y visita `http://ipam.example.com` (ajusta según tu dominio o IP) para finalizar la instalación web de PHPIPAM.

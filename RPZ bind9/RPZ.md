Para esto abrimos la consola de ubuntu e ingresamos en modo root
```
sudo su -
```
Vamos a la carpeta /etc/bind/
```
cd /etc/bind/
```
Editamos el archivo named.conf.local
```
nano named.conf.local
```
Luego agregamos esto al final del archivo
```
zone "rpz.local" {
    type master;
    file "/etc/bind/db.rpz.local";
    allow-query { "none"; };
    allow-transfer { "none"; };
};
```
comprobamos que la configuración esté bien con 
```
named-checkconf
```
Si todo está bien no debería dar salida, ahora procedemos a crear la base de datos de la zona, es un archivo SOA el cual se llamará db.rpz.local
```
nano db.rpz.local
```
Una vez dentro del editor procedemos a insertar una zona SOA la cual tendrá el siguiente contenido
```
```
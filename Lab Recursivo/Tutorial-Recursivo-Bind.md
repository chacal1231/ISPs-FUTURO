# Instalar DNS recursivo bind9

Para esto abrimos la consola de ubuntu e ingresamos en modo root
```
sudo su -
```
Ingresamos la contraseña y actualizo los repositorios
```
apt update
```
luego instalamos el paquete bind9
```
apt install bind9 bind9utils bind9-doc
```
Vamos al directorio /etc/bind:
```
cd /etc/bind
```
Este directorio es el encargado de la configuración de bind, ahora editaremos el archivo **named.conf.options**
```
nano named.conf.options
```
Por defecto bind no viene como resolver, agregaremos las opciones para que resuelva en las interfaces dichas tanto IPv4 como IPv6, adicional crearemos un ACL para que solo IPs permitidas puedan tener respuesta recursiva.

```
options {
	directory "/var/cache/bind";

	// If there is a firewall between you and nameservers you want
	// to talk to, you may need to fix the firewall to allow multiple
	// ports to talk. See http://www.kb.cert.org/vuls/id/800113

	// If your ISP provided one or more IP addresses for stable 
	// nameservers, you probably want to use them as forwarders.  
	// Uncomment the following block, and insert the addresses replacing 
	// the all-0's placeholder.

	// forwarders {
	// 	0.0.0.0;
	// };

	//========================================================================
	// If BIND logs error messages about the root key being expired,
	// you will need to update your keys. See https://www.isc.org/bind-keys
	//========================================================================
	dnssec-validation auto; <--- activo DNSSEC y bind automaticamente genera y mantienes las llaves desde los servidores root
	managed-keys-directory "/var/lib/bind/dnssec"; <--- Directorio donde se guardaran las keys del DNS
	listen-on port 53 { any; };	    <--- escuchamos en el puerto 53 en cualquier interface en IPv4
	listen-on-v6 port 53 { any; };  <--- escuchamos en el puerto 53 en cualquier interface en IPv6
	
	allow-query { localhost; 100.64.0.0/10; fdce:7632::/32; };		<--- ACL, responderemos solo a host en esos rangos 

	recursion yes;		<--- Le decimos que vamos a responder de manera recursiva
};
```
Luego debemos validar la configuración, para ello tenemos el siguiente comando, si este no devuelve nada significa que no encontró errores en la configuración:

```
# named-checkconf
```

Reiniciamos el servicio 

```
# systemctl restart bind9
```

Y comprobamos el estado de bind9:

```
# systemctl status bind9
```


Deberíamos obtener algo parecido:

```
● named.service - BIND Domain Name Server
   Loaded: loaded (/lib/systemd/system/named.service; enabled; vendor preset: enabled)
  Drop-In: /etc/systemd/system/service.d
       └─lxc.conf
   Active: **active (running)** since Thu 2024-05-13 01:38:27 UTC; 4s ago
    Docs: man:named(8)
  Main PID: 849 (named)
   Tasks: 50 (limit: 152822)
   Memory: 103.2M
   CGroup: /system.slice/named.service
       └─849 /usr/sbin/named -f -u bind

May 13 01:38:27 resolv.mac-tel.co named[849]: **command channel listening on ::1#953**
May 13 01:38:27 resolv.mac-tel.co named[849]: managed-keys-zone: loaded serial 6
May 13 01:38:27 resolv.mac-tel.co named[849]: zone 0.in-addr.arpa/IN: loaded serial 1
May 13 01:38:27 resolv.mac-tel.co named[849]: zone 127.in-addr.arpa/IN: loaded serial 1
May 13 01:38:27 resolv.mac-tel.co named[849]: zone localhost/IN: loaded serial 2
May 13 01:38:27 resolv.mac-tel.co named[849]: zone 255.in-addr.arpa/IN: loaded serial 1
May 13 01:38:27 resolv.mac-tel.co named[849]: **all zones loaded**
May 13 01:38:27 resolv.mac-tel.co named[849]: **running**
May 13 01:38:27 resolv.mac-tel.co named[849]: managed-keys-zone: Key 20326 for zone . is now trusted (acceptance timer>
May 13 01:38:27 resolv.mac-tel.co named[849]: resolver priming query complete
```

Con esto ya tenemos nuestro dns recursivo andando, para comprobar su funcionamiento utilizaremos dig





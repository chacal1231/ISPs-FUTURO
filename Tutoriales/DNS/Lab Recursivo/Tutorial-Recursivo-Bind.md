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
	qname-minimization relaxed; <--- Activo qname-minimization para que solo envie parte del dominio consultado y tenga mejor rendimiento en la consulta.
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

Con esto ya tenemos nuestro dns recursivo andando, para comprobar su funcionamiento utilizaremos dig y los servidores raiz quemados en bind

```
dig @localhost

; <<>> DiG 9.16.48-Ubuntu <<>> @localhost
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 41236
;; flags: qr rd ra ad; QUERY: 1, ANSWER: 13, AUTHORITY: 0, ADDITIONAL: 27

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 1232
; COOKIE: cdffe4158c376661010000006654c785f5bc92faf92bf95e (good)
;; QUESTION SECTION:
;.                              IN      NS

;; ANSWER SECTION:
.                       517873  IN      NS      a.root-servers.net.
.                       517873  IN      NS      d.root-servers.net.
.                       517873  IN      NS      f.root-servers.net.
.                       517873  IN      NS      l.root-servers.net.
.                       517873  IN      NS      j.root-servers.net.
.                       517873  IN      NS      b.root-servers.net.
.                       517873  IN      NS      m.root-servers.net.
.                       517873  IN      NS      e.root-servers.net.
.                       517873  IN      NS      c.root-servers.net.
.                       517873  IN      NS      i.root-servers.net.
.                       517873  IN      NS      g.root-servers.net.
.                       517873  IN      NS      h.root-servers.net.
.                       517873  IN      NS      k.root-servers.net.

;; ADDITIONAL SECTION:
a.root-servers.net.     517873  IN      A       198.41.0.4
b.root-servers.net.     517873  IN      A       170.247.170.2
c.root-servers.net.     517873  IN      A       192.33.4.12
d.root-servers.net.     517873  IN      A       199.7.91.13
e.root-servers.net.     517873  IN      A       192.203.230.10
f.root-servers.net.     517873  IN      A       192.5.5.241
g.root-servers.net.     517873  IN      A       192.112.36.4
h.root-servers.net.     517873  IN      A       198.97.190.53
i.root-servers.net.     517873  IN      A       192.36.148.17
j.root-servers.net.     517873  IN      A       192.58.128.30
k.root-servers.net.     517873  IN      A       193.0.14.129
l.root-servers.net.     517873  IN      A       199.7.83.42
m.root-servers.net.     517873  IN      A       202.12.27.33
a.root-servers.net.     517873  IN      AAAA    2001:503:ba3e::2:30
b.root-servers.net.     517873  IN      AAAA    2801:1b8:10::b
c.root-servers.net.     517873  IN      AAAA    2001:500:2::c
d.root-servers.net.     517873  IN      AAAA    2001:500:2d::d
e.root-servers.net.     517873  IN      AAAA    2001:500:a8::e
f.root-servers.net.     517873  IN      AAAA    2001:500:2f::f
g.root-servers.net.     517873  IN      AAAA    2001:500:12::d0d
h.root-servers.net.     517873  IN      AAAA    2001:500:1::53
i.root-servers.net.     517873  IN      AAAA    2001:7fe::53
j.root-servers.net.     517873  IN      AAAA    2001:503:c27::2:30
k.root-servers.net.     517873  IN      AAAA    2001:7fd::1
l.root-servers.net.     517873  IN      AAAA    2001:500:9f::42
m.root-servers.net.     517873  IN      AAAA    2001:dc3::35
```

Ahora preguntaremos quien es google

```
dig @localhost google.com
```

Nos dará como respuesta algo como esto 

```
root@dns:/etc/bind# dig google.com @localhost

; <<>> DiG 9.16.48-Ubuntu <<>> google.com @localhost
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 24214
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 1232
; COOKIE: b523c33698614990010000006654c3c18abbfa340cc13ef5 (good)
;; QUESTION SECTION:
;google.com.                    IN      A

;; ANSWER SECTION:
google.com.             116     IN      A       142.250.78.174

;; Query time: 0 msec
;; SERVER: 127.0.0.1#53(127.0.0.1)
;; WHEN: Mon May 27 17:32:49 UTC 2024
;; MSG SIZE  rcvd: 83
```
qr: Indica que este es un mensaje de respuesta.

rd: Indica que la consulta solicitó recursión.

ra: Indica que el servidor permite y ha realizado la recursión.


Con esto hemos terminado el laboratorio de servidor recursivo en ubuntu con Bind9
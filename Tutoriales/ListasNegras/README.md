# Hardening ISP — MikroTik RouterOS v7 (IPv4) para no caer en listas negras

**Objetivo:** reducir el riesgo de que IPs, prefijos o el ASN del ISP terminen en listas negras por open resolver, open proxy, amplificación, spam, spoofing o clientes comprometidos.

**Alcance:** borde ISP / CGNAT / BNG con **RouterOS v7**, **solo IPv4**. IPv6 queda como fase 2 (obligatoria si anuncias espacio v6 — hasta entonces tu hardening es bypasseable por familia).

Ajusta interfaces, prefijos, bloque NOC y excepciones a tu red antes de pegar.

---

## 0. Por qué cae un ISP en listas (resumen)

| Causa | Lista típica | Mitigación en esta guía |
|---|---|---|
| DNS recursivo abierto | DNSBL, DDoS feeds | §4, §5 |
| Proxy / SOCKS abierto | abuse feeds | §5 |
| Amplificación NTP/SNMP/SSDP/memcached/chargen | UCEPROTECT, blocklist.de | §5 |
| Cliente infectado spam TCP/25 | Spamhaus XBL/CSS, SBL | §6 |
| Spoofing de origen | reflexión DDoS, reputación ASN | §7 |
| CGNAT sin trazabilidad | no se puede limpiar el abuso | §10 |
| Gestión expuesta | compromiso del propio equipo | §3 |
| PTR/abuse/RPKI mal | reputación de correo y routing | §11 |

> Regla de oro: ningún cliente sale con IPs que no le pertenecen, y ningún router de borde opera como resolver, proxy o reflector abierto.

---

## 1. Interface lists base

```rsc
/interface list
add name=WAN comment="Uplinks publicos"
add name=LAN comment="Clientes / red interna"

/interface list member
add list=WAN interface=ether1
add list=LAN interface=bridge-lan
```

Mete a `WAN` cada uplink (incl. `pppoe-out`, `vlan-transito`, `sfp-sfpplus1`) y a `LAN` cada interfaz de clientes (`vlan-clientes`, `vlan-cgnat`, `vlan-empresariales`).

---

## 2. Address-lists de apoyo

```rsc
/ip firewall address-list
add list=NOC address=TU-BLOQUE-NOC/24 comment="Red de gestion NOC"

# Bogons / origenes invalidos hacia Internet (BCP38)
add list=BOGONS address=0.0.0.0/8
add list=BOGONS address=10.0.0.0/8
add list=BOGONS address=127.0.0.0/8
add list=BOGONS address=169.254.0.0/16
add list=BOGONS address=172.16.0.0/12
add list=BOGONS address=192.0.0.0/24
add list=BOGONS address=192.0.2.0/24
add list=BOGONS address=192.168.0.0/16
add list=BOGONS address=198.18.0.0/15
add list=BOGONS address=198.51.100.0/24
add list=BOGONS address=203.0.113.0/24
add list=BOGONS address=224.0.0.0/4
add list=BOGONS address=240.0.0.0/4
```

> `100.64.0.0/10` (CGNAT) **no** va en BOGONS si este equipo lo usa internamente. Bloquéalo solo donde no deba aparecer.

---

## 3. Apagar servicios y endurecer el plano de gestión

```rsc
/ip proxy  set enabled=no
/ip socks  set enabled=no

/ip service
set telnet  disabled=yes
set ftp     disabled=yes
set www     disabled=yes
set api     disabled=yes
set api-ssl disabled=yes
set ssh     address=TU-BLOQUE-NOC/24
set winbox  address=TU-BLOQUE-NOC/24

# Plano de gestión L2 / discovery (lo que el firewall L3 no cubre)
/tool bandwidth-server set enabled=no
/tool mac-server set allowed-interface-list=LAN
/tool mac-server mac-winbox set allowed-interface-list=LAN
/tool mac-server ping set enabled=no
/ip neighbor discovery-settings set discover-interface-list=LAN
/tool romon set enabled=no
```

Si usas el web-proxy internamente, déjalo encendido pero bloquéalo desde WAN (§5).

---

## 4. DNS

Lo ideal en un ISP es **no** resolver desde el router: usa Unbound/Knot/BIND dedicado con rate-limiting (RRL). Si aun así el MikroTik resuelve para la LAN:

```rsc
/ip dns set allow-remote-requests=yes cache-size=4096KiB
```

Nunca debe responder desde Internet — el bloqueo lo hace el firewall (§5). Si lo dejas como resolver, considera RRL para que ni un host LAN comprometido lo use de palanca de amplificación.

---

## 5. Firewall input — orden correcto

El orden importa. De arriba hacia abajo:

```rsc
/ip firewall filter

# --- Base ---
add chain=input action=accept connection-state=established,related comment="ACCEPT est/related"
add chain=input action=drop   connection-state=invalid comment="DROP invalid"
add chain=input action=accept src-address-list=NOC comment="ACCEPT gestion NOC"

# --- ICMP (monitoreo + PMTUD): aceptar antes de cualquier drop de WAN ---
add chain=input action=accept protocol=icmp limit=50,10:packet comment="ACCEPT ICMP rate-limited"

# --- (Opcional) BGP si este equipo levanta eBGP con upstream ---
# add chain=input action=accept in-interface-list=WAN protocol=tcp dst-port=179 \
#     src-address-list=BGP-PEERS comment="ACCEPT BGP upstreams"

# --- DNS permitido solo desde LAN (si el router resuelve) ---
add chain=input action=accept in-interface-list=LAN protocol=udp dst-port=53 comment="DNS LAN UDP"
add chain=input action=accept in-interface-list=LAN protocol=tcp dst-port=53 comment="DNS LAN TCP"

# --- DNS recursivo abierto: DROP desde WAN ---
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=53 comment="DROP DNS ext UDP"
add chain=input action=drop in-interface-list=WAN protocol=tcp dst-port=53 comment="DROP DNS ext TCP"

# --- Proxy / SOCKS abiertos ---
add chain=input action=drop in-interface-list=WAN protocol=tcp dst-port=8080 comment="DROP web-proxy ext"
add chain=input action=drop in-interface-list=WAN protocol=tcp dst-port=1080 comment="DROP SOCKS ext"

# --- Amplificacion / reflexion UDP ---
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=123   comment="NTP monlist amp"
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=161   comment="SNMP amp/leak"
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=1900  comment="SSDP amp"
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=11211 comment="memcached amp"
add chain=input action=drop in-interface-list=WAN protocol=udp dst-port=19    comment="chargen amp"

# --- Cierre del acceso al router desde WAN ---
add chain=input action=drop in-interface-list=WAN comment="DROP acceso al router desde WAN"
```

> El `drop` final de WAN es seguro para CGNAT/BNG. Si el equipo levanta BGP/OSPF/BFD y **el peer inicia la sesión**, descomenta el accept de 179 (el `established,related` solo te salva si la sesión la inicia siempre el MikroTik).

---

## 6. Anti-spam: SMTP TCP/25 desde clientes

```rsc
/ip firewall filter

# Excepcion: MTAs legitimos (por IP del servidor, NUNCA por /24 del cliente)
add chain=forward action=accept protocol=tcp dst-port=25 \
    src-address-list=SMTP-PERMITIDO in-interface-list=LAN out-interface-list=WAN \
    comment="ACCEPT SMTP MTA legitimo"

add chain=forward action=drop protocol=tcp dst-port=25 \
    in-interface-list=LAN out-interface-list=WAN \
    comment="DROP SMTP saliente clientes (anti-spam)"
```

```rsc
/ip firewall address-list
add list=SMTP-PERMITIDO address=38.x.x.x/32 comment="Servidor mail autorizado"
```

No bloquees **587** (submission) ni **465** (SMTPS) autenticados — no son vector de spam masivo. Para autorizar un MTA: PTR válido, SPF, DKIM/DMARC, que no sea open relay, responsable documentado y monitoreo de volumen.

---

## 7. Anti-spoofing (BCP38) — uRPF como baseline

Lo escalable es uRPF estricto, no una regla por cliente:

```rsc
/ip settings set rp-filter=strict
```

Solo donde haya **ruteo asimétrico** (multihoming de cliente) y `strict` rompa tráfico legítimo, usa ACL explícito por interfaz como excepción documentada:

```rsc
/ip firewall address-list add list=CLIENTE-XYZ address=38.191.220.0/24
/ip firewall filter
add chain=forward in-interface=vlan-cliente-xyz src-address-list=!CLIENTE-XYZ \
    action=drop comment="Anti-spoof Cliente XYZ (asimetrico)"
```

Refuerzo con bogons hacia Internet:

```rsc
/ip firewall filter
add chain=forward in-interface-list=LAN out-interface-list=WAN \
    src-address-list=BOGONS action=drop comment="DROP bogons/RFC1918 hacia Internet"
add chain=forward in-interface-list=LAN src-address-type=!unicast \
    action=drop comment="DROP non-unicast desde clientes"
```

---

## 8. FastTrack — orden seguro

FastTrack saltea el resto del `forward` para esa conexión. Todo lo crítico (drop SMTP, anti-spoof, bogons, suspendidos, **y la detección de infectados**) debe ir **antes**:

```rsc
/ip firewall filter
# ...(SMTP, anti-spoof, bogons, deteccion ya colocados arriba)...
add chain=forward action=fasttrack-connection connection-state=established,related \
    comment="FASTTRACK est/related"
add chain=forward action=accept connection-state=established,related \
    comment="ACCEPT est/related"
```

---

## 9. Detección de clientes posiblemente infectados

Debe ir **antes** del FastTrack o no cuenta las conexiones:

```rsc
/ip firewall filter
add chain=forward protocol=tcp connection-limit=200,32 src-address-list=!WHITELIST \
    action=add-src-to-address-list address-list=POSIBLE-INFECTADO \
    address-list-timeout=1h comment="DETECT exceso de conexiones"
```

Revisar, no bloquear en automático si hay NATs empresariales detrás:

```rsc
/ip firewall address-list print where list=POSIBLE-INFECTADO
```

Señales típicas de bot a vigilar en NetFlow/Akvorado: ráfagas salientes a 23, 2323, 22, 445, 3389, 5060, 25.

---

## 10. Bloqueo temporal de abuso

```rsc
/ip firewall address-list add list=ABUSE-BLOCK address=38.x.x.x timeout=1d
/ip firewall filter add chain=forward src-address-list=ABUSE-BLOCK action=drop \
    comment="DROP IP abusiva temporal"
```

Blackhole solo si la IP no es de un cliente activo:

```rsc
/ip route add dst-address=38.x.x.x/32 type=blackhole
```

---

## 11. CGNAT con trazabilidad real

Logging por conexión a escala de carrier funde el equipo. Usa **NAT determinístico (port-block)**: asignas un rango de puertos fijo por IP privada, así calculas qué cliente tenía un puerto a una hora **sin logs**, que es lo que te exigirán en una queja.

```rsc
/ip firewall nat
add chain=srcnat src-address=100.64.0.0/10 action=src-nat \
    to-addresses=38.x.x.1-38.x.x.50 comment="CGNAT pool (idealmente port-block determinista)"
```

Buenas prácticas: separar pools por POP/zona, no mezclar residencial y corporativo, NTP correcto en todos los routers (sin hora exacta la traza no sirve), documentar asignaciones.

---

## 12. Reputación fuera del router (no es firewall pero te lista igual)

- **PTR/rDNS** consistente en todo el espacio público; convención que distinga estático de dinámico. Registra el espacio residencial/CGNAT en el **Spamhaus PBL** tú mismo.
- **abuse@ / noc@ / postmaster@** funcionando, `abuse-c` correcto en LACNIC, y un proceso real de abuse desk (una queja ignorada convierte un XBL puntual en SBL de /24).
- **RPKI/ROA** al día: `38.191.192.0/19 origin AS273103 max-length /24`. No evita spam pero protege la reputación de routing del ASN.

---

## 13. Checklist de producción

```text
[ ] WAN/LAN clasificadas correctamente
[ ] DNS no responde desde Internet (UDP+TCP 53 WAN drop)
[ ] Proxy y SOCKS no expuestos
[ ] Amplificacion cerrada: 123, 161, 1900, 11211, 19
[ ] TCP/25 bloqueado a clientes; excepciones por IP de MTA
[ ] rp-filter=strict activo; ACL solo donde hay asimetria
[ ] Bogons hacia Internet bloqueados
[ ] ICMP permitido antes del drop final de WAN
[ ] BGP/179 aceptado si el equipo es border
[ ] Gestion (ssh/winbox/api/mac-server/romon) solo NOC/LAN
[ ] CGNAT determinista o con trazabilidad
[ ] NTP correcto en todos los routers
[ ] PTR, abuse-c, RPKI/ROA en orden
[ ] Deteccion de infectados antes de FastTrack
[ ] Contadores de firewall revisados
[ ] FASE 2 pendiente: replicar todo en IPv6
```

---

## 14. Auditoría rápida

```rsc
/ip service print
/ip proxy print
/ip socks print
/ip dns print
/ip settings print
/ip firewall filter print stats
/ip firewall nat print
/ip firewall address-list print where list=POSIBLE-INFECTADO
/ip firewall connection print where dst-port=53
/ip firewall connection print where dst-port=8080
/ip firewall connection print where dst-port=1080
/ip firewall connection print where dst-port=25
```

Validación externa (desde fuera de tu red) — que estén **cerrados**:
`53/UDP, 53/TCP, 8080, 1080, 25, 123/UDP, 161/UDP, 1900/UDP, 11211/UDP, 8291, 8728, 8729, 21, 23`.
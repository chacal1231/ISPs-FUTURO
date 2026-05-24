# ISPs-FUTURO

Repositorio de documentacion, laboratorios y herramientas practicas para operacion de redes ISP, NOC e infraestructura de servicios.

El contenido esta organizado para que un tecnico o administrador pueda encontrar rapidamente guias de instalacion, monitoreo, DNS, telefonia, gestion IP y utilidades de diagnostico.

## Contenido

```text
ISPs-FUTURO/
├── Herramientas/
│   └── ListasNegras/
└── Tutoriales/
    ├── Asterisk/
    ├── DNS/
    │   ├── Lab Recursivo/
    │   ├── Monitoreo DNS/
    │   └── RPZ bind9/
    ├── PHPIPAM/
    ├── Ripe ATLAS/
    └── Zabbix/
```

## Herramientas

| Herramienta | Descripcion | Ruta |
|-------------|-------------|------|
| ListasNegras DNSBL | Frontend web local para revisar IPv4 y rangos CIDR contra listas negras DNSBL publicas. Permite ver riesgo, hits, detalle TXT y generar reportes. | [Herramientas/ListasNegras](Herramientas/ListasNegras/README.md) |

## Tutoriales

### DNS

| Guia | Descripcion | Ruta |
|------|-------------|------|
| DNS recursivo con Bind9 | Laboratorio para instalar y configurar un resolver recursivo Bind9 en Ubuntu, con ACL, DNSSEC, qname minimization y pruebas con `dig`. | [Tutoriales/DNS/Lab Recursivo](Tutoriales/DNS/Lab%20Recursivo/Tutorial-Recursivo-Bind.md) |
| RPZ en Bind9 | Guia para configurar una zona RPZ local en Bind9 y validar la configuracion con `named-checkconf`. | [Tutoriales/DNS/RPZ bind9](Tutoriales/DNS/RPZ%20bind9/RPZ.md) |
| Monitoreo DNS | Instalacion de Prometheus, bind_exporter y Grafana para monitorear Bind9, con imagenes de referencia y dashboard. | [Tutoriales/DNS/Monitoreo DNS](Tutoriales/DNS/Monitoreo%20DNS/Grafana%20+%20Prometheus%20bind9.md) |

### Infraestructura y monitoreo

| Guia | Descripcion | Ruta |
|------|-------------|------|
| Zabbix 7.4 + PostgreSQL 17 | Instalacion de PostgreSQL 17 y Zabbix 7.4 en Ubuntu 24.04, incluyendo base de datos, servidor, frontend web y agente. | [Tutoriales/Zabbix](Tutoriales/Zabbix/Guia-20250906.md) |
| PHPIPAM | Instalacion de PHPIPAM en Ubuntu con MariaDB, Apache, modulos PHP, VirtualHost, permisos y tareas cron. | [Tutoriales/PHPIPAM](Tutoriales/PHPIPAM/Guia%20instalaci%C3%B3n%20PHPIPAM.md) |
| RIPE Atlas Software Probe | Instalacion de una sonda RIPE Atlas por paquete `.deb` en Debian 11, con validacion SHA256 y registro de la sonda. | [Tutoriales/Ripe ATLAS/Sonda Software](Tutoriales/Ripe%20ATLAS/Sonda%20Software/Tutorial%2020250711.md) |

### Telefonia

| Guia | Descripcion | Ruta |
|------|-------------|------|
| Asterisk 23 desde source | Procedimiento NOC para compilar, instalar y poner en produccion Asterisk 23 en Ubuntu/Debian, con usuario de servicio, permisos, audios IVR y checklist. | [Tutoriales/Asterisk](Tutoriales/Asterisk/README.md) |

## Requisitos generales

La mayoria de guias estan orientadas a servidores Linux, especialmente Ubuntu Server y Debian. Dependiendo del laboratorio se requieren privilegios `root` o `sudo`, acceso a consola y conectividad a internet para instalar paquetes.

Para la herramienta de ListasNegras se requiere Python 3.9+ y las dependencias indicadas en su propio README.

## Uso recomendado

1. Entra a la carpeta del tema que necesitas.
2. Lee la guia completa antes de ejecutar comandos en produccion.
3. Ajusta dominios, IPs, contrasenas, ACL y rutas segun tu red.
4. Prueba primero en laboratorio cuando el cambio afecte servicios criticos como DNS, PBX, monitoreo o base de datos.

## Notas de seguridad

- No copies contrasenas de ejemplo en entornos reales.
- Restringe acceso administrativo por firewall, VPN o ACL.
- Valida cada archivo de configuracion antes de reiniciar servicios.
- Mantiene respaldos de configuraciones criticas antes de modificar sistemas en produccion.
- Revisa la politica de cada herramienta externa o servicio publico antes de automatizar consultas frecuentes.

## Contribuciones

Las mejoras son bienvenidas. Puedes aportar nuevas guias, corregir pasos, actualizar versiones, agregar capturas o proponer herramientas utiles para operacion ISP/NOC.

Para mantener el repositorio ordenado:

- Usa Markdown para las guias.
- Incluye objetivo, requisitos, pasos, validacion y notas.
- Guarda imagenes junto a la guia que las utiliza.
- Evita subir entornos virtuales, caches, credenciales, backups o reportes generados.

## Licencias

Cada herramienta o componente puede declarar su propia licencia. La herramienta [ListasNegras](Herramientas/ListasNegras/README.md) se publica bajo licencia MIT.

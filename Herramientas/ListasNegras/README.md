# DNSBL Scanner

Escaner open source para revisar direcciones IPv4 y rangos CIDR contra listas negras DNSBL publicas.

Este fork separa el motor de escaneo del entorno privado original. El resultado se muestra en consola con una tabla visual y tambien puede generar un reporte HTML navegable.

## Estructura

```text
ListasNegras-OpenSource/
├── CheckListas.py
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Instalacion

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso rapido

Escanear una IP:

```bash
python3 main.py 8.8.8.8
```

Escanear varias IPs:

```bash
python3 main.py 8.8.8.8 1.1.1.1 203.0.113.10
```

Escanear un rango CIDR:

```bash
python3 main.py 203.0.113.0/29
```

Usar un archivo:

```bash
python3 main.py --file targets.txt
```

El archivo puede contener una IP o CIDR por linea. Las lineas vacias y las que empiezan por `#` se ignoran.

## Salida visual

La consola muestra un resumen por IP:

```text
DNSBL scan results
IPs scanned: 2 | DNSBL zones: 67 | Listed IPs: 1 | Hits: 3 | Time: 4.22s

IP               RISK     HITS    VISUAL               BLACKLISTS
--------------------------------------------------------------------------------------------
203.0.113.10     ALTO     3       [#.................]  Spamhaus ZEN, CBL, Spamcop
8.8.8.8          BAJO     0       [..................]  -
```

Tambien genera un reporte HTML en `reports/` con KPIs, tabla de riesgo, barras visuales y detalle de cada DNSBL que respondio.

## Opciones utiles

```bash
python3 main.py 8.8.8.8 --json reports/result.json
python3 main.py 203.0.113.0/24 --max-hosts 512
python3 main.py 8.8.8.8 --no-html
python3 main.py 8.8.8.8 --fail-on-listed
```

## Criterio de riesgo

| Hits DNSBL | Riesgo |
|------------|--------|
| 0 | LOW / BAJO |
| 1-2 | MEDIUM / MEDIO |
| 3 o mas | HIGH / ALTO |

## Dependencias

- Python 3.9+
- dnspython

## Notas

- Solo se soporta IPv4 porque las DNSBL consultadas usan el formato de IPv4 invertida.
- Algunas DNSBL pueden bloquear consultas frecuentes o requerir registro previo.
- Un listing no siempre significa abuso activo. Use el detalle TXT y la politica de cada lista para tomar decisiones.
- Los rangos CIDR grandes pueden generar muchas consultas DNS. Ajuste `--max-hosts`, `--concurrency` y `--timeout` segun su red.

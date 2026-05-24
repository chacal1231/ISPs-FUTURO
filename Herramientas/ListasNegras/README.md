# DNSBL Scanner Web

Frontend web local para revisar direcciones IPv4 y rangos CIDR contra listas negras DNSBL publicas.

El proyecto se ejecuta desde `main.py`. Desde el navegador se ingresan los objetivos, se configura el escaneo y se consultan los resultados.

## Estructura

```text
ListasNegras/
├── CheckListas.py
├── main.py
├── requirements.txt
├── reports/
└── README.md
```

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En Linux o macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

Ejecuta solamente:

```bash
python main.py
```

Luego abre:

```text
http://127.0.0.1:8000
```

La aplicacion intenta abrir el navegador automaticamente. Si prefieres no abrirlo:

```bash
python main.py --no-browser
```

Tambien puedes cambiar host o puerto:

```bash
python main.py --host 0.0.0.0 --port 8080
```

## Que se puede hacer desde el frontend

- Ingresar una o varias IPv4.
- Ingresar rangos CIDR.
- Ajustar `max hosts`, `timeout` y concurrencia.
- Ejecutar el escaneo contra las DNSBL.
- Ver KPIs, riesgo por IP, hits y detalle TXT de cada lista.
- Guardar un reporte HTML en `reports/`.
- Guardar un JSON con el ultimo resultado.

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
- Un listado no siempre significa abuso activo. Usa el detalle TXT y la politica de cada lista para tomar decisiones.
- Los rangos CIDR grandes pueden generar muchas consultas DNS. Ajusta `max hosts`, concurrencia y timeout desde el frontend.

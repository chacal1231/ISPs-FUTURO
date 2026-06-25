# Tutorial: Instalación local de Microsoft Connected Cache para ISP

## 1. Objetivo

Este documento sirve como guía interna para preparar, registrar, crear y desplegar un nodo local de **Microsoft Connected Cache for ISPs (MCC)** dentro de la red de un operador.

Microsoft Connected Cache permite almacenar contenido de Microsoft localmente dentro de la red del ISP, reduciendo consumo de tránsito/peering externo y mejorando la experiencia de descarga para los usuarios finales.

Contenido que puede cachear:

- Actualizaciones de Windows.
- Actualizaciones de Microsoft 365 / Office Click-to-Run.
- Aplicaciones y actualizaciones de Microsoft Store.
- Definiciones de Microsoft Defender.
- Contenido de Xbox Game Pass para PC.

> Nota: MCC complementa el peering con Microsoft/AS8075. Aunque el ISP tenga peering con Microsoft, parte del contenido estático se entrega desde CDNs externas y puede beneficiarse del cache local.

---

## 2. Requisitos previos

Antes de iniciar el proceso, se debe validar que el ISP cumpla con los siguientes requisitos.

### 2.1 Requisitos del operador

- Tener **ASN propio**.
- Tener el registro activo y actualizado en **PeeringDB**.
- Tener acceso al correo del **NOC registrado en PeeringDB**.
- El correo NOC debe estar operativo, ya que Microsoft enviará allí el código de verificación.
- Tener una cuenta de Azure con acceso administrativo.
- Tener una suscripción **Azure Pay-As-You-Go** activa.
- Tener tarjeta de crédito para activar Pay-As-You-Go.

> Aunque Microsoft Connected Cache es un servicio gratuito para operadores, Microsoft exige una suscripción Pay-As-You-Go para poder hacer el onboarding del servicio.

### 2.2 Requisitos IP / Red

- Se requiere conectividad IPv4 pública hacia el servidor de cache.
- Microsoft Connected Cache para ISP **solo soporta IPv4 actualmente**.
- No soporta IPv6 para la configuración del cache.
- Se recomienda usar un enlace o direccionamiento dedicado, por ejemplo un **/31 IPv4** entre el router del ISP y el servidor de cache.
- Definir previamente si el enrutamiento de clientes será:
  - Manual por bloques CIDR.
  - Dinámico por BGP/iBGP.

### 2.3 Requisitos del servidor

Microsoft indica que el servidor debe estar instalado sobre:

- **Ubuntu 24.04 LTS**.

Requisitos mínimos recomendados para iniciar:

- CPU: 8 cores o superior.
- RAM: 16 GB o superior.
- Disco para cache: mínimo 100 GB.
- Recomendado: SSD/NVMe para mejor rendimiento.
- Conectividad de red estable hacia el core del ISP.

Recomendación por tipo de despliegue:

| Escenario | Tráfico pico estimado | Recomendación |
|---|---:|---|
| Edge / ISP pequeño | < 5 Gbps | VM o servidor con hasta 8 cores, 16 GB RAM y SSD de 500 GB |
| Metro POP | 5 a 20 Gbps | 16 cores, 32 GB RAM, 2 a 3 SSD de 500 GB |
| Data Center | 20 a 40 Gbps | 32+ cores, 64+ GB RAM, 4 a 6 SSD/NVMe de 500 GB a 1 TB |

---

## 3. Preparación inicial

### 3.1 Validar PeeringDB

Ingresar a PeeringDB y revisar:

- ASN correcto del operador.
- Nombre de la organización.
- Estado activo.
- Contacto NOC configurado.
- Correo NOC actualizado.
- Acceso real al buzón del NOC.

Microsoft utilizará la información registrada en PeeringDB para validar que el solicitante corresponde al operador del ASN.

### 3.2 Activar Azure Pay-As-You-Go

1. Ingresar al portal de Azure.
2. Crear o seleccionar la cuenta de la organización.
3. Activar una suscripción **Pay-As-You-Go**.
4. Asociar una tarjeta de crédito.
5. Validar que la suscripción quede activa.

> Importante: No seleccionar servicios adicionales innecesarios durante el registro para evitar cargos no deseados.

### 3.3 Preparar servidor Ubuntu

Actualizar el sistema:

```bash
sudo apt update && sudo apt upgrade -y
```

Verificar versión del sistema:

```bash
lsb_release -a
```

Debe mostrar Ubuntu 24.04 LTS.

Configurar hostname recomendado:

```bash
sudo hostnamectl set-hostname mcc-cache-pop01
```

Crear punto de montaje para cache:

```bash
sudo mkdir -p /cache/mcc
sudo chmod 777 /cache/mcc
```

> El directorio de cache debe tener permisos completos y estar montado sobre el disco destinado para almacenamiento de contenido.

Validar disco:

```bash
df -h
lsblk
```

---

## 4. Registro del operador en Microsoft Connected Cache

### 4.1 Crear recurso en Azure

1. Ingresar al portal de Azure.
2. Seleccionar **Create a Resource**.
3. Buscar **Microsoft Connected Cache**.
4. Seleccionar **Create**.
5. Elegir:
   - Suscripción.
   - Resource Group.
   - Región.
   - Nombre del recurso.
6. Crear el recurso.
7. Esperar que finalice el deployment.
8. Seleccionar **Go to resource**.

### 4.2 Proceso de Sign Up

Dentro del recurso de Microsoft Connected Cache:

1. Ir a **Settings > Sign up**.
2. Ingresar el ASN de la organización.
3. Indicar si el operador también presta tránsito a otros ASNs.
4. Si aplica, agregar los ASNs downstream.
5. Enviar la solicitud.

Microsoft validará la información contra PeeringDB.

### 4.3 Verificación por correo NOC

Microsoft enviará un código de verificación al correo NOC registrado en PeeringDB.

1. Revisar el correo NOC.
2. Buscar correo de:

```text
microsoft-noreply@microsoft.com
```

Asunto esperado:

```text
Here's your Microsoft Connected Cache verification code
```

3. Copiar el código.
4. En Azure ir a:

```text
Microsoft Connected Cache > Settings > Verify operator
```

5. Pegar el código de verificación.
6. Completar la validación.

> Los códigos de verificación expiran en 24 horas. Si expira, se debe generar un nuevo código.

---

## 5. Crear nodo de cache

Después de validar el operador:

1. Entrar al recurso de Microsoft Connected Cache en Azure.
2. Ir a **Settings > Cache nodes**.
3. Seleccionar **Create Cache Node**.
4. Asignar nombre al nodo.

Ejemplo de nombre:

```text
mcc-bogota-odata-01
```

5. Crear el nodo.

---

## 6. Configuración del nodo de cache

Durante la configuración del nodo se deben definir los parámetros de operación.

### 6.1 Capacidad de salida

Configurar el máximo egress permitido según la capacidad real del servidor y del enlace.

Ejemplo:

```text
Max egress: 5 Gbps
```

No se recomienda configurar una capacidad superior a la que realmente soportan:

- NIC del servidor.
- Disco/NVMe.
- CPU.
- Puerto del switch.
- Red de transporte interna.

### 6.2 Directorio de cache

Indicar el path donde se almacenará el contenido:

```text
/cache/mcc
```

Validar que el directorio exista y tenga permisos:

```bash
sudo mkdir -p /cache/mcc
sudo chmod 777 /cache/mcc
```

### 6.3 Método de enrutamiento de clientes

Microsoft Connected Cache permite dos métodos.

#### Opción A: Routing manual por CIDR

Se cargan manualmente los bloques IPv4 de clientes que deben ser atendidos por el cache.

Ejemplo:

```text
38.191.192.0/24
38.191.198.0/24
190.90.0.0/24
```

Usar esta opción cuando:

- El ISP tiene pocos bloques.
- Se quiere iniciar con una prueba controlada.
- No se desea activar BGP inicialmente.

#### Opción B: Routing por BGP/iBGP

Microsoft Connected Cache incluye Bird BGP y puede establecer sesiones iBGP con routers, route servers o route collectors internos del operador.

Usar esta opción cuando:

- El ISP tiene múltiples bloques.
- El operador presta tránsito a otros ASNs.
- Se quiere que el cache aprenda dinámicamente los prefijos alcanzables.
- Se requiere operación escalable.

Consideraciones:

- El ASN usado debe ser el mismo validado durante el registro.
- Se configura la vecindad BGP desde Azure y desde el router del operador.
- Cuando BGP esté establecido correctamente, el portal dejará de mostrar `0` en Prefix Count/IP Space.

Ejemplo conceptual:

```text
Cache Node IPv4: 10.10.10.2/31
Router ISP IPv4: 10.10.10.1/31
ASN ISP: 273103
BGP: iBGP
```

## 7. Descargar e instalar el paquete de provisión

Después de configurar el nodo en Azure:

1. Ir a la pestaña **Server provisioning**.
2. Seleccionar **Download provisioning package**.
3. Copiar el paquete al servidor Ubuntu.
4. Entrar al directorio donde se descargó el instalador.
5. Dar permisos al script:

```bash
sudo chmod +x provisionmcc.sh
```

6. Copiar y ejecutar el comando que muestra Azure Portal.

Ejemplo:

```bash
sudo ./provisionmcc.sh
```

> El comando real debe copiarse desde el portal de Azure, porque incluye identificadores y llaves únicas del nodo.

Durante la instalación, Microsoft instala y utiliza componentes como:

- Azure IoT Edge.
- Moby/container runtime.
- Contenedores necesarios para Microsoft Connected Cache.

Aunque se usa IoT Edge, el objetivo es administrar el ciclo de vida del contenedor del cache y reportar estado hacia Azure.

---

## 98. Validaciones posteriores

### 8.1 Validar servicios

```bash
sudo systemctl status aziot-edged
sudo iotedge list
```

Validar contenedores:

```bash
sudo docker ps
```

O si el runtime usa Moby:

```bash
sudo iotedge list
```

### 8.2 Validar disco de cache

```bash
df -h /cache/mcc
sudo du -sh /cache/mcc
```

### 8.3 Validar conectividad IPv4

```bash
ping -c 4 8.8.8.8
curl -4 ifconfig.me
```

### 8.4 Validar BGP si aplica

En el router del ISP:

```rsc
/routing/bgp/session/print
/routing/route/print where bgp
```

En Azure Portal:

- Revisar estado del cache node.
- Revisar Prefix Count.
- Revisar IP Space.
- Revisar estado de health/usage.

---

## 9. Checklist de implementación

| Ítem | Estado |
|---|---|
| ASN activo | Pendiente |
| PeeringDB actualizado | Pendiente |
| Correo NOC validado | Pendiente |
| Acceso al correo NOC confirmado | Pendiente |
| Azure Pay-As-You-Go activo | Pendiente |
| Tarjeta de crédito asociada | Pendiente |
| Servidor con Ubuntu 24.04 LTS | Pendiente |
| Disco de cache montado | Pendiente |
| Directorio `/cache/mcc` creado | Pendiente |
| IPv4 pública o /31 configurado | Pendiente |
| Método de routing definido | Pendiente |
| Operador verificado en Azure | Pendiente |
| Cache node creado | Pendiente |
| Provisioning package descargado | Pendiente |
| Script ejecutado | Pendiente |
| Servicio validado | Pendiente |
| BGP/manual routing validado | Pendiente |
| Primer tráfico observado | Pendiente |

---

## 10. Troubleshooting básico

### No llega el correo de verificación

Revisar:

- Que el correo NOC en PeeringDB esté correcto.
- Carpeta de spam.
- Reglas de filtrado del correo.
- Que el dominio permita correos desde:

```text
microsoft-noreply@microsoft.com
```

### Azure no permite continuar el registro

Validar:

- Suscripción Pay-As-You-Go activa.
- Usuario con permisos suficientes.
- ASN correctamente ingresado.
- PeeringDB activo y actualizado.

### El cache no instala

Validar:

- Ubuntu 24.04 LTS.
- Disco montado correctamente.
- Directorio de cache con permisos.
- Salida a Internet desde el servidor.
- Fecha/hora/NTP correcto.

Comandos útiles:

```bash
timedatectl
sudo apt update
sudo journalctl -u aziot-edged -f
sudo iotedge list
```

### BGP no levanta

Validar:

- IP local y remota.
- ASN correcto.
- Firewall entre router y cache.
- Que la sesión sea IPv4.
- Que ambos lados usen el ASN esperado.
- Que no exista bloqueo TCP/179.

---

## 11. Recomendaciones operativas

- Iniciar con routing manual o con un conjunto pequeño de prefijos para validar comportamiento.
- Medir consumo antes y después del despliegue.
- Monitorear CPU, RAM, disco, NIC y throughput.
- Usar SSD/NVMe para evitar cuello de botella en disco.
- No anunciar prefijos de clientes que no deban usar ese nodo.
- Crear un nodo por POP principal si el tráfico lo justifica.
- Mantener el correo NOC de PeeringDB actualizado.
- Documentar cada cache node con POP, IP, ASN, capacidad y prefijos asociados.

---

## 12. Fuentes oficiales

- Microsoft Connected Cache for ISPs overview:  
  https://learn.microsoft.com/en-us/windows/deployment/do/mcc-isp-overview

- Operator sign up and service onboarding:  
  https://learn.microsoft.com/en-us/windows/deployment/do/mcc-isp-signup

- Create, configure, provision, and deploy the cache node:  
  https://learn.microsoft.com/en-us/windows/deployment/do/mcc-isp-create-provision-deploy

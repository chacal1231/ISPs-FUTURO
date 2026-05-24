#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

# Variables
PROMETHEUS_VERSION="2.52.0"
BIND_EXPORTER_VERSION="0.7.0"
GRAFANA_VERSION="10.0.0" # Ajusta según la última versión estable
USER="prometheus"
GROUP="prometheus"
BIND_STATS_PORT="8053"
BIND_EXPORTER_PORT="9153"

# Función para instalar Prometheus
install_prometheus() {
  echo "Instalando Prometheus..."
  wget https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
  tar xzf prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
  mv prometheus-${PROMETHEUS_VERSION}.linux-amd64 /etc/prometheus

  # Crear servicio systemd para Prometheus
  cat <<EOF > /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/etc/prometheus/prometheus --config.file=/etc/prometheus/prometheus.yml
Restart=always

[Install]
WantedBy=multi-user.target
EOF

  # Recargar daemon y habilitar servicio
  systemctl daemon-reload
  systemctl enable prometheus
  systemctl start prometheus
  echo "Prometheus instalado y en ejecución."
}

# Función para instalar Bind Exporter
install_bind_exporter() {
  echo "Instalando Bind Exporter..."
  wget https://github.com/prometheus-community/bind_exporter/releases/download/v${BIND_EXPORTER_VERSION}/bind_exporter-${BIND_EXPORTER_VERSION}.linux-amd64.tar.gz
  tar xzf bind_exporter-${BIND_EXPORTER_VERSION}.linux-amd64.tar.gz
  mv bind_exporter-${BIND_EXPORTER_VERSION}.linux-amd64 /etc/bind_exporter

  # Crear servicio systemd para Bind Exporter
  cat <<EOF > /etc/systemd/system/bind_exporter.service
[Unit]
Description=Bind Exporter
Wants=network-online.target
After=network-online.target

[Service]
ExecReload=/bin/kill -HUP \$MAINPID
ExecStart=/etc/bind_exporter/bind_exporter \\
  --bind.pid-file=/var/run/named/named.pid \\
  --bind.timeout=20s \\
  --web.listen-address=0.0.0.0:${BIND_EXPORTER_PORT} \\
  --web.telemetry-path=/metrics \\
  --bind.stats-url=http://127.0.0.1:${BIND_STATS_PORT}/ \\
  --bind.stats-groups=server,view,tasks
Restart=always

[Install]
WantedBy=multi-user.target
EOF

  # Recargar daemon y habilitar servicio
  systemctl daemon-reload
  systemctl enable bind_exporter
  systemctl start bind_exporter
  echo "Bind Exporter instalado y en ejecución."
}

# Función para configurar Bind9
configure_bind9() {
  echo "Configurando Bind9 para exportar estadísticas..."
  # Añadir el canal de estadísticas a la configuración de Bind9
  if ! grep -q "statistics-channels" /etc/bind/named.conf.options; then
    cat <<EOF >> /etc/bind/named.conf.options

statistics-channels {
  inet 127.0.0.1 port ${BIND_STATS_PORT} allow { 127.0.0.1; };
};
EOF
  fi

  # Reiniciar Bind9 para aplicar cambios
  systemctl restart bind9
  echo "Bind9 configurado correctamente."
}

# Función para instalar Grafana
install_grafana() {
  echo "Instalando Grafana..."
  sudo apt-get install -y adduser libfontconfig1 musl
  wget https://dl.grafana.com/enterprise/release/grafana-enterprise_11.0.0_amd64.deb
  sudo dpkg -i grafana-enterprise_11.0.0_amd64.deb
  sudo /bin/systemctl daemon-reload
  sudo /bin/systemctl enable grafana-server
  systemctl restart grafana-server
}

# Función principal
main() {
  # Actualizar repositorios e instalar dependencias
  echo "Actualizando repositorios e instalando dependencias..."
  apt-get update
  apt-get install -y wget tar

  # Llamar a las funciones de instalación y configuración
  install_prometheus
  install_bind_exporter
  configure_bind9
  install_grafana

  echo "Proceso completado. Prometheus, Bind Exporter y Grafana han sido instalados y configurados correctamente."
}

# Ejecutar función principal
main

#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
STATE_DIR="${SCRIPT_DIR}/state"

if [[ ! -r "${ENV_FILE}" ]]; then
  echo "Error: no existe o no se puede leer ${ENV_FILE}" >&2
  echo "Copia .env.example como .env y configura las credenciales." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

mkdir -p "${STATE_DIR}" "${SCRIPT_DIR}/output" "${SCRIPT_DIR}/logs"
chmod 700 "${STATE_DIR}"
exec 9>"${STATE_DIR}/cron.lock"
if ! /usr/bin/flock -n 9; then
  echo "Otra ejecución de CorreosCogent sigue activa; se omite esta ronda."
  exit 0
fi

exec /usr/bin/python3 "${SCRIPT_DIR}/cogent_email.py" "$@"

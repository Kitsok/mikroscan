#!/usr/bin/with-contenv bashio

set -euo pipefail

APP_DIR="/opt/mikroscan"
PERSIST_ROOT="/data/mikroscan"

mkdir -p "${PERSIST_ROOT}/data" "${PERSIST_ROOT}/logs"
rm -rf "${APP_DIR}/data" "${APP_DIR}/logs"
ln -s "${PERSIST_ROOT}/data" "${APP_DIR}/data"
ln -s "${PERSIST_ROOT}/logs" "${APP_DIR}/logs"

BACKEND="$(bashio::config 'backend')"
API_PORT="$(bashio::config 'api_port')"
SSH_PORT="$(bashio::config 'ssh_port')"
API_SSL="$(bashio::config 'api_ssl')"
VERBOSE="$(bashio::config 'verbose')"
DEVICE_USERNAME="$(bashio::config 'device_username')"
DEVICE_PASSWORD="$(bashio::config 'device_password')"

if [[ -n "${DEVICE_USERNAME}" && -z "${DEVICE_PASSWORD}" ]]; then
  bashio::log.fatal "device_password must be set when device_username is provided"
  exit 1
fi

if [[ -z "${DEVICE_USERNAME}" && -n "${DEVICE_PASSWORD}" ]]; then
  bashio::log.fatal "device_username must be set when device_password is provided"
  exit 1
fi

ARGS=(
  "main.py"
  "--serve"
  "--host" "0.0.0.0"
  "--web-port" "8099"
  "--backend" "${BACKEND}"
)

if [[ "${BACKEND}" == "api" ]]; then
  ARGS+=("--api-port" "${API_PORT}")
  if [[ "${API_SSL}" == "true" ]]; then
    ARGS+=("--api-ssl")
  else
    ARGS+=("--no-api-ssl")
  fi
else
  ARGS+=("--ssh-port" "${SSH_PORT}")
fi

if [[ "${VERBOSE}" == "true" ]]; then
  ARGS+=("--verbose")
fi

if [[ -n "${DEVICE_USERNAME}" ]]; then
  ARGS+=("-u" "${DEVICE_USERNAME}" "-p" "${DEVICE_PASSWORD}")
fi

export MIKROSCAN_ALLOWED_CLIENTS="172.30.32.2,127.0.0.1,::1"

bashio::log.info "Starting Mikroscan app"
cd "${APP_DIR}"
exec python3 "${ARGS[@]}"

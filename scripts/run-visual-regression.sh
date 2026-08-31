#!/usr/bin/env bash

set -euo pipefail

readonly PLAYWRIGHT_VERSION="1.62.1"
readonly PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble"
readonly EDIT_PORT=2738
readonly RUN_PORT=2739

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT
readonly FRONTEND_ROOT="${REPO_ROOT}/frontend"
readonly FIXTURE="e2e-tests/py/visual_tokens.py"

for command in curl docker uv; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Required command not found: ${command}" >&2
    exit 1
  fi
done

if [[ ! -x "${FRONTEND_ROOT}/node_modules/.bin/playwright" ]]; then
  echo "Playwright is not installed. Run 'pnpm install' first." >&2
  exit 1
fi

ACTUAL_PLAYWRIGHT_VERSION="$(
  "${FRONTEND_ROOT}/node_modules/.bin/playwright" --version
)"
ACTUAL_PLAYWRIGHT_VERSION="${ACTUAL_PLAYWRIGHT_VERSION#Version }"
if [[ "${ACTUAL_PLAYWRIGHT_VERSION}" != "${PLAYWRIGHT_VERSION}" ]]; then
  echo \
    "Playwright package ${ACTUAL_PLAYWRIGHT_VERSION} does not match image ${PLAYWRIGHT_VERSION}." \
    >&2
  exit 1
fi

for port in "${EDIT_PORT}" "${RUN_PORT}"; do
  if command -v lsof >/dev/null 2>&1 &&
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${port} is already in use." >&2
    exit 1
  fi
done

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/marimo-visual-regression.XXXXXX")"
readonly CONFIG_ROOT="${LOG_DIR}/config"
EDIT_PID=""
RUN_PID=""

cleanup() {
  local pid
  for pid in "${EDIT_PID}" "${RUN_PID}"; do
    if [[ -n "${pid}" ]]; then
      kill "${pid}" >/dev/null 2>&1 || true
      wait "${pid}" >/dev/null 2>&1 || true
    fi
  done
  rm -rf "${LOG_DIR}"
}
trap cleanup EXIT INT TERM

wait_for_server() {
  local name="$1"
  local url="$2"
  local log_file="$3"

  for _ in {1..120}; do
    if curl --fail --silent --output /dev/null "${url}"; then
      return 0
    fi
    sleep 0.25
  done

  echo "${name} server did not become ready: ${url}" >&2
  sed -n '1,160p' "${log_file}" >&2
  return 1
}

(
  cd "${FRONTEND_ROOT}"
  exec env XDG_CONFIG_HOME="${CONFIG_ROOT}" \
    _MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE=true \
    uv run marimo -q edit -p "${EDIT_PORT}" --headless --no-token
) >"${LOG_DIR}/edit.log" 2>&1 &
EDIT_PID="$!"

(
  cd "${FRONTEND_ROOT}"
  exec env XDG_CONFIG_HOME="${CONFIG_ROOT}" \
    _MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE=true \
    uv run marimo -q run "${FIXTURE}" -p "${RUN_PORT}" --headless --no-token
) >"${LOG_DIR}/run.log" 2>&1 &
RUN_PID="$!"

wait_for_server \
  "Edit" \
  "http://127.0.0.1:${EDIT_PORT}/?file=${FIXTURE}" \
  "${LOG_DIR}/edit.log"
wait_for_server \
  "Read" \
  "http://127.0.0.1:${RUN_PORT}" \
  "${LOG_DIR}/run.log"

docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  --volume "${REPO_ROOT}:/work" \
  --workdir /work/frontend \
  "${PLAYWRIGHT_IMAGE}" \
  /work/frontend/node_modules/.bin/playwright test \
  --config=e2e-tests/visual-regression.container.config.ts \
  "$@"

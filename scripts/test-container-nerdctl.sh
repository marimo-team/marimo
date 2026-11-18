#!/usr/bin/env bash
set -euo pipefail

version=2.4.2
case "$HOSTTYPE" in
  x86_64)
    architecture=amd64
    sha256=1f12c1a5840744fdf7029483c55a69813d44aa2ec1ef879d52d81ff6a3049ecd
    ;;
  aarch64)
    architecture=arm64
    sha256=fe0ef0e9840ee8932640e6058f84b7fa98050f9726e44af44883a5b804ae830e
    ;;
  *)
    echo "Unsupported nerdctl test architecture: $HOSTTYPE" >&2
    exit 1
    ;;
esac

runtime_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/marimo-nerdctl.XXXXXXXX")
runtime=(
  sudo --non-interactive env
  "PATH=$runtime_dir/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  "NERDCTL_TOML=$runtime_dir/nerdctl.toml"
  CONTAINERD_NAMESPACE=marimo-contract
)
daemon_launcher=
bridge="mcb${runtime_dir##*.}"
cleanup() {
  local status=$?
  if [[ -f "$runtime_dir/containerd.pid" ]]; then
    local daemon_pid
    read -r daemon_pid < "$runtime_dir/containerd.pid"
    sudo --non-interactive kill "$daemon_pid" 2>/dev/null || true
  fi
  if [[ -n "$daemon_launcher" ]]; then
    wait "$daemon_launcher" || true
  fi
  if ip link show dev "$bridge" >/dev/null 2>&1 &&
     ! sudo --non-interactive ip link delete dev "$bridge" type bridge; then
    status=1
  fi
  if (( status != 0 )) && [[ -f "$runtime_dir/containerd.log" ]]; then
    tail -n 40 "$runtime_dir/containerd.log" >&2
  fi
  sudo --non-interactive rm -rf -- "$runtime_dir"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

archive="nerdctl-full-$version-linux-$architecture.tar.gz"
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/containerd/nerdctl/releases/download/v$version/$archive" \
  --output "$runtime_dir/$archive"
printf '%s  %s\n' "$sha256" "$runtime_dir/$archive" | sha256sum --check
tar -xzf "$runtime_dir/$archive" -C "$runtime_dir" \
  bin/containerd bin/containerd-shim-runc-v2 bin/nerdctl bin/runc libexec/cni

printf 'version = 3\n' > "$runtime_dir/containerd.toml"
cat > "$runtime_dir/nerdctl.toml" <<CONFIG
address = "unix://$runtime_dir/containerd.sock"
cni_path = "$runtime_dir/libexec/cni"
cni_netconfpath = "$runtime_dir/net.d"
data_root = "$runtime_dir/nerdctl"
CONFIG

# The default network must be named bridge. Use a separate interface and
# lease directory so the contract cannot change another nerdctl network.
mkdir "$runtime_dir/net.d"
subnet="10.$((RANDOM % 256)).$((RANDOM % 256)).0/24"
cat > "$runtime_dir/net.d/nerdctl-bridge.conflist" <<CONFIG
{
  "cniVersion": "1.0.0",
  "name": "bridge",
  "nerdctlLabels": {"nerdctl/default-network": "true"},
  "plugins": [
    {
      "type": "bridge",
      "bridge": "$bridge",
      "isGateway": true,
      "ipMasq": true,
      "ipam": {"type": "host-local", "dataDir": "$runtime_dir/ipam",
               "ranges": [[{"subnet": "$subnet"}]]}
    },
    {"type": "portmap", "capabilities": {"portMappings": true}}
  ]
}
CONFIG

# The root shell records its own PID before it becomes containerd.
# shellcheck disable=SC2016
"${runtime[@]}" bash -c 'echo "$$" > "$1"; shift; exec "$@"' _ \
  "$runtime_dir/containerd.pid" "$runtime_dir/bin/containerd" \
  --config "$runtime_dir/containerd.toml" \
  --root "$runtime_dir/root" \
  --state "$runtime_dir/state" \
  --address "$runtime_dir/containerd.sock" \
  > "$runtime_dir/containerd.log" 2>&1 &
daemon_launcher=$!

for ((attempt = 0; attempt < 20; attempt++)); do
  if [[ -S "$runtime_dir/containerd.sock" ]]; then
    break
  fi
  sleep 1
done
"${runtime[@]}" nerdctl version
"${runtime[@]}" nerdctl info >/dev/null

"${runtime[@]}" MARIMO_TEST_CONTAINER_ENGINE=nerdctl \
  "${UV_PROJECT_ENVIRONMENT:-.venv}/bin/python" -m pytest -q \
  tests/_cli/test_container_engine.py "$@"

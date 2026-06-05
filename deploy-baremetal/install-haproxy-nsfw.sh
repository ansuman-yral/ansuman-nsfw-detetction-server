#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "run as root: sudo $0" >&2
  exit 1
fi

cfg_path="${HAPROXY_CFG:-/etc/haproxy/haproxy.cfg}"
map_path="${HAPROXY_HOST_MAP:-/etc/haproxy/maps/host2backend.map}"
host_name="nsfw.ansuman.yral.com"
backend_name="be_nsfw_app"
bridge_port="18082"
local_app_port="8001"
begin_marker="# BEGIN YRAL NSFW INGRESS"
end_marker="# END YRAL NSFW INGRESS"

node_ip="${TAILSCALE_NODE_IP:-}"
if [[ -z "$node_ip" ]]; then
  node_ip="$(hostname -I | tr ' ' '\n' | grep '^100\.' | head -n 1 || true)"
fi
if [[ -z "$node_ip" ]]; then
  echo "could not determine Tailscale node IP; set TAILSCALE_NODE_IP" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$cfg_path" "${cfg_path}.bak-nsfw-${timestamp}"
cp -a "$map_path" "${map_path}.bak-nsfw-${timestamp}"

if ! grep -qF "$begin_marker" "$cfg_path"; then
  cat >> "$cfg_path" <<EOF

$begin_marker
frontend fe_nsfw_bridge
    bind 127.0.0.1:${bridge_port}
    bind ${node_ip}:${bridge_port}
    mode http
    option httplog
    default_backend be_local_nsfw_app

backend be_local_nsfw_app
    mode http
    option httpchk GET /health
    option forwardfor if-none
    http-check expect status 200
    http-request set-header X-Real-IP %[src] if !{ req.hdr(X-Real-IP) -m found }
    http-request set-header X-Forwarded-Proto http if !{ req.hdr(X-Forwarded-Proto) -m found }
    server local_nsfw 127.0.0.1:${local_app_port} check

backend be_nsfw_app
    mode http
    balance roundrobin
    option httpchk GET /health
    option forwardfor if-none
    http-check expect status 200
    http-request set-header X-Forwarded-Proto https if { ssl_fc }
    http-request set-header X-Forwarded-Proto http if !{ ssl_fc }
    http-request set-header X-Real-IP %[req.hdr(CF-Connecting-IP)] if { req.hdr(CF-Connecting-IP) -m found }
    http-request set-header X-Forwarded-For %[req.hdr(CF-Connecting-IP)] if { req.hdr(CF-Connecting-IP) -m found }
    http-request set-header X-Real-IP %[src] if !{ req.hdr(CF-Connecting-IP) -m found }
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    http-response set-header X-Frame-Options "DENY"
    http-response set-header X-Content-Type-Options "nosniff"
    http-response set-header Referrer-Policy "strict-origin-when-cross-origin"
    server ansuman1 100.78.17.101:${bridge_port} check
    server ansuman2 100.79.99.107:${bridge_port} check
$end_marker
EOF
else
  echo "HAProxy NSFW block already present in $cfg_path"
fi

if ! grep -qE "^${host_name}[[:space:]]+" "$map_path"; then
  printf '%s %s\n' "$host_name" "$backend_name" >> "$map_path"
else
  echo "HAProxy host map entry already present in $map_path"
fi

haproxy -c -f "$cfg_path"

if command -v systemctl >/dev/null 2>&1; then
  systemctl reload haproxy
else
  service haproxy reload
fi

echo "HAProxy configured for ${host_name}"

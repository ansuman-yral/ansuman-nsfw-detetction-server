# NSFW Bare Metal Deployment

This mirrors the `ai-feed-recommendation-system` bare-metal flow:

- GitHub Actions builds and pushes `ghcr.io/<repo>:<sha>`.
- Deployment files are synced to `/home/ansuman/nsfw` on each server.
- `docker compose up -d --no-deps app` rolls servers one at a time.
- The container listens on `8080`; the host publishes it on `127.0.0.1:8001`.
- HAProxy should expose `nsfw.ansuman.yral.com` through bridge port `18082`.
- GitHub Actions should SSH to public IPs, not Tailscale IPs:
  `BAREMETAL_SERVER_IPS=88.99.192.144,88.99.61.221`.
- HAProxy backend routing still uses Tailscale IPs:
  `100.78.17.101` and `100.79.99.107`.

Apply HAProxy on both `ansuman-1` and `ansuman-2`:

```bash
sudo /home/ansuman/nsfw/install-haproxy-nsfw.sh
```

The script appends a marked block and map entry only if missing. It backs up
the existing config/map, validates HAProxy, and reloads the service.

For manual changes, use `haproxy-nsfw-snippets.cfg` and
`host2backend.map.append`.

Validate HAProxy before reload:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

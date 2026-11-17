# Deploy with nginx

nginx is a popular web server that can be used as a reverse proxy for web applications. This guide will show you how to deploy marimo behind an nginx reverse proxy.

## Prerequisites

- A marimo notebook or app that you want to deploy
- nginx installed on your server
- Basic understanding of nginx configuration

## Configuration

Create a new configuration file in `/etc/nginx/conf.d/` (e.g., `marimo.conf`):

```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_set_header    Host $http_host;
        proxy_set_header    X-Real-IP $remote_addr;
        proxy_set_header    X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header    X-Forwarded-Proto $scheme;
        proxy_pass          http://127.0.0.1:2718;

        # Required for WebSocket support
        proxy_http_version  1.1;
        proxy_set_header    Upgrade $http_upgrade;
        proxy_set_header    Connection "upgrade";
        proxy_read_timeout  600;
    }

    # Optional: Serve static files
    location /static/ {
        alias /path/to/your/static/files/;
    }
}
```

## Breaking it down

- `server_name`: Replace with your domain name
- `proxy_pass`: Points to your marimo application (default port is 2718)
- `Host $http_host`: Preserves the public hostname and port
- `X-Forwarded-Proto $scheme`: Passes the public HTTP or HTTPS scheme to marimo
- WebSocket support: The following lines are required for marimo to function properly:

  ```nginx
  proxy_http_version  1.1;
  proxy_set_header    Upgrade $http_upgrade;
  proxy_set_header    Connection "upgrade";
  ```

- `proxy_read_timeout`: Increased to 600 seconds to handle long-running operations

## Running your application

1. Start your marimo application:

```bash
marimo run app.py --host 127.0.0.1 --port 2718 --allow-origins http://your-domain.com
```

Replace `http://your-domain.com` with the public origin that users open in their browser.
For HTTPS, use `https://your-domain.com`.
These options also apply to `marimo edit`.

2. Test your nginx configuration:

```bash
nginx -t
```

3. Reload nginx to apply changes:

```bash
nginx -s reload
```

Your marimo application should now be accessible at your domain.

## SSL/HTTPS

For production deployments, it's recommended to use HTTPS. You can use [Certbot](https://certbot.eff.org/) to automatically configure SSL with Let's Encrypt certificates.

## Common Issues

### WebSocket connection returns HTTP 403

WebSocket connections use the public origin from the browser.
A proxy can change the `Host` header or the scheme before the request reaches marimo.
This can cause the origin comparison to fail.

If the public hostname differs from `--host`, set `--allow-origins` to the public origin.
This configuration also applies when the proxy changes `Host`:

```bash
marimo run app.py --host 127.0.0.1 --port 2718 --allow-origins https://your-domain.com
```

An origin contains a scheme and a hostname, plus a port for non-default ports, such as `https://your-domain.com:8443`.
It has no path or trailing slash, even for applications with a `--base-url`.
For multiple public origins, repeat `--allow-origins`.
The `X-Forwarded-Host` header does not replace this configuration.

For HTTPS connections, retain `proxy_set_header X-Forwarded-Proto $scheme` in nginx.
Uvicorn uses this header only from trusted proxies.
If nginx connects from an address other than `127.0.0.1`, set `FORWARDED_ALLOW_IPS` to the proxy addresses before you start marimo.
Use a comma-separated list of the proxy addresses, as described in [Uvicorn's configuration](https://uvicorn.dev/settings/#http).

### Kernel Not Found

If you see a "kernel not found" error, ensure that:

1. WebSocket support is properly configured in your nginx configuration
2. The proxy headers are correctly set
3. Your marimo application is running and accessible at the specified proxy_pass address

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
        proxy_set_header    Host $host;
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
marimo run app.py --host 127.0.0.1 --port 2718
```

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

### Kernel Not Found

If you see a "kernel not found" error, ensure that:

1. WebSocket support is properly configured in your nginx configuration
2. The proxy headers are correctly set
3. Your marimo application is running and accessible at the specified proxy_pass address

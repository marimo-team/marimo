/* Copyright 2026 Marimo. All rights reserved. */

const net = require("node:net");

const port = Number(process.argv[2]);
const upstreamPort = Number(process.argv[3]);

if (!Number.isInteger(port) || !Number.isInteger(upstreamPort)) {
  throw new Error(
    `Expected integer ports, received ${process.argv[2]} and ${process.argv[3]}`,
  );
}

net
  .createServer((client) => {
    const upstream = net.connect({
      host: "host.docker.internal",
      port: upstreamPort,
    });

    client.pipe(upstream).pipe(client);
    client.on("error", () => upstream.destroy());
    upstream.on("error", () => client.destroy());
  })
  .listen(port, "127.0.0.1");

import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import WebSocket from "ws";
import { createWebSocketServer } from "./index";

describe("LSP WebSocket security", () => {
  it("requires a private token before listening", () => {
    expect(() => createWebSocketServer(0, "")).toThrow("MARIMO_LSP_TOKEN");
  });

  it.each([
    {},
    { "Marimo-LSP-Token": "" },
    { "Marimo-LSP-Token": "wrong" },
    { "Marimo-LSP-Token": "xxxxxxxxxx" },
    { "Marimo-LSP-Token": "test-token-extra" },
    { "Marimo-LSP-Token": "tést-token" },
    { "Marimo-LSP-Token": "test-token, test-token" },
    { Origin: "https://attacker.test" },
    { "Marimo-LSP-Token": "test-token", Origin: "http://evil.example.com" },
    { "Marimo-LSP-Token": "test-token", Origin: "https://attacker.test" },
    { "Marimo-LSP-Token": "test-token", Origin: "null" },
    { "Marimo-LSP-Token": "test-token", Origin: "http://127.0.0.1" },
    { "Marimo-LSP-Token": "test-token", Origin: "" },
    { "Marimo-LSP-Token": ["test-token", "test-token"] },
    { "Marimo-LSP-Token": ["wrong", "test-token"] },
    { "Marimo-LSP-Token": ["test-token", "wrong"] },
  ])("rejects direct connections: %j", async (headers) => {
    const server = createWebSocketServer(0, "test-token");
    await once(server, "listening");
    const address = server.address() as AddressInfo;
    expect(address.address).toBe("127.0.0.1");
    let connections = 0;
    server.on("connection", () => connections++);
    const client = new WebSocket(`ws://127.0.0.1:${address.port}`, { headers });
    try {
      const [error] = await once(client, "error");
      expect(error.message).toContain("403");
      // Rejected handshakes must not emit a connection event.
      expect(connections).toBe(0);
      // Rejection must leave the listener usable, including with lowercase headers.
      const validClient = new WebSocket(`ws://127.0.0.1:${address.port}`, {
        headers: { "marimo-lsp-token": "test-token" },
      });
      try {
        await once(validClient, "open");
        expect(connections).toBe(1);
      } finally {
        validClient.terminate();
      }
    } finally {
      client.terminate();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });

  it("authenticates before spawning through the production bridge", async () => {
    const directory = await mkdtemp(join(tmpdir(), "marimo-lsp-security-"));
    const marker = join(directory, "spawned.json");
    const script = join(directory, "language-server.cjs");
    const recorder = join(directory, "record-spawns.cjs");
    await writeFile(script, "process.stdin.resume();");
    // Record at the actual spawn boundary so even short-lived children count.
    await writeFile(
      recorder,
      `
      const cp = require("node:child_process");
      const originalSpawn = cp.spawn;
      cp.spawn = (command, args, options) => {
        const env = options?.env ?? process.env;
        require("node:fs").appendFileSync(${JSON.stringify(marker)}, JSON.stringify({
          hasToken: Object.hasOwn(env, "MARIMO_LSP_TOKEN"),
          otherEnv: env.MARIMO_LSP_TEST,
        }) + "\\n");
        return originalSpawn(command, args, options);
      };
    `,
    );
    const reservation = createServer();
    reservation.listen(0, "127.0.0.1");
    await once(reservation, "listening");
    const { port } = reservation.address() as AddressInfo;
    await new Promise<void>((resolve) => reservation.close(() => resolve()));

    const bridge = spawn(
      process.execPath,
      [
        "--require",
        recorder,
        "./dist/index.cjs",
        "--port",
        String(port),
        "--lsp",
        `copilot:${script}`,
        "--log-file",
        join(directory, "bridge.log"),
      ],
      {
        env: {
          ...process.env,
          MARIMO_LSP_TOKEN: "test-token",
          MARIMO_LSP_TEST: "preserved",
        },
        stdio: "ignore",
      },
    );
    const exited = once(bridge, "exit");
    let validClient: WebSocket | undefined;
    try {
      for (const headers of [
        {},
        { "Marimo-LSP-Token": "wrong" },
        { "Marimo-LSP-Token": "test-token", Origin: "https://attacker.test" },
      ]) {
        await vi.waitFor(async () => {
          expect(bridge.exitCode).toBeNull();
          const client = new WebSocket(`ws://127.0.0.1:${port}`, { headers });
          try {
            const [error] = await once(client, "error");
            expect(error.message).toContain("403");
          } finally {
            client.terminate();
          }
        });
        expect(existsSync(marker)).toBe(false);
      }

      validClient = new WebSocket(`ws://127.0.0.1:${port}`, {
        headers: { "Marimo-LSP-Token": "test-token" },
      });
      await once(validClient, "open");
      await vi.waitFor(async () => {
        const spawns = (await readFile(marker, "utf8"))
          .trim()
          .split("\n")
          .map((line) => JSON.parse(line));
        expect(spawns).toEqual([{ hasToken: false, otherEnv: "preserved" }]);
      });
    } finally {
      validClient?.terminate();
      bridge.kill();
      await exited;
      await rm(directory, { recursive: true, force: true });
    }
  });

  it("isolates an abruptly disconnected client", async () => {
    const server = createWebSocketServer(0, "test-token");
    await once(server, "listening");
    const address = server.address() as AddressInfo;
    server.on("connection", (socket) => {
      socket.on("message", (data) => socket.send(data));
    });
    const clients = Array.from(
      { length: 2 },
      () =>
        new WebSocket(`ws://127.0.0.1:${address.port}`, {
          headers: { "Marimo-LSP-Token": "test-token" },
        }),
    );
    try {
      await Promise.all(clients.map((client) => once(client, "open")));
      const closed = once(clients[0], "close");
      clients[0].terminate();
      await closed;
      clients[1].send("still available");
      const [message] = await once(clients[1], "message");
      expect(message.toString()).toBe("still available");
    } finally {
      for (const client of clients) client.terminate();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });

  it("allows the authenticated proxy to exchange messages", async () => {
    const server = createWebSocketServer(0, "test-token");
    await once(server, "listening");
    const address = server.address() as AddressInfo;
    server.on("connection", (socket) => {
      socket.on("message", (data) => socket.send(data));
    });
    const client = new WebSocket(`ws://127.0.0.1:${address.port}/lsp/ty`, {
      headers: { "Marimo-LSP-Token": "test-token" },
    });
    try {
      await once(client, "open");
      client.send("hello");
      const [message] = await once(client, "message");
      expect(message.toString()).toBe("hello");
    } finally {
      client.close();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });
});

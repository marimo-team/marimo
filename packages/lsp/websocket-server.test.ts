import { once } from "node:events";
import type { AddressInfo } from "node:net";
import { describe, expect, it } from "vitest";
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
      // No language-server process can be created before this event.
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

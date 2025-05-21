import type * as http from "node:http";
import parseArgs from "minimist";
import type ws from "ws";
import { WebSocketServer } from "ws";
import type * as rpc from "@sourcegraph/vscode-ws-jsonrpc";
import * as rpcServer from "@sourcegraph/vscode-ws-jsonrpc/lib/server";
import path from "node:path";

// Adapted from https://github.com/wylieconlon/jsonrpc-ws-proxy

const argv = parseArgs(process.argv.slice(2));

if (argv.help) {
  console.log("Usage: index.js --port 3000");
  process.exit(1);
}

const serverPort: number = Number.parseInt(argv.port) || 3000;

const languageServers: Record<string, string[]> = {
  copilot: ["node", path.join(__dirname, "language-server.js"), "--stdio"],
};

function toSocket(webSocket: ws): rpc.IWebSocket {
  return {
    send: (content) => {
      try {
        webSocket.send(content);
      } catch (error) {
        console.error("[ERROR] Failed to send message:", error);
      }
    },
    onMessage: (cb) =>
      (webSocket.onmessage = (event) => {
        try {
          console.log("[DEBUG] Received message:", event.data);
          cb(event.data);
        } catch (error) {
          console.error("[ERROR] Error processing message:", error);
        }
      }),
    onError: (cb) =>
      (webSocket.onerror = (event) => {
        console.error("[ERROR] WebSocket error:", event);
        if ("message" in event) {
          cb(event.message);
        }
      }),
    onClose: (cb) =>
      (webSocket.onclose = (event) => {
        console.log(
          `[INFO] WebSocket closed with code ${event.code}, reason: ${event.reason}`,
        );
        cb(event.code, event.reason);
      }),
    dispose: () => {
      try {
        webSocket.close();
      } catch (error) {
        console.error("[ERROR] Error closing WebSocket:", error);
      }
    },
  };
}

// Add error handling for WebSocket server creation
try {
  const wss = new WebSocketServer(
    {
      port: serverPort,
      perMessageDeflate: false,
    },
    () => {
      console.log(`[INFO] WebSocket server listening on port ${serverPort}`);
    },
  );

  wss.on("error", (error) => {
    console.error("[ERROR] WebSocket server error:", error);
  });

  wss.on("connection", (client: ws, request: http.IncomingMessage) => {
    console.log(`[INFO] New connection from ${request.socket.remoteAddress}`);

    let langServer: string[] | undefined;

    Object.keys(languageServers).forEach((key) => {
      if (request.url === `/${key}`) {
        langServer = languageServers[key];
        console.log(`[INFO] Matched language server: ${key}`);
      }
    });

    if (!langServer || !langServer.length) {
      console.error(
        `[ERROR] Invalid language server requested: ${request.url}`,
      );
      client.close();
      return;
    }

    try {
      const localConnection = rpcServer.createServerProcess(
        "local",
        langServer[0],
        langServer.slice(1),
      );
      console.log(
        `[INFO] Created language server process: ${langServer.join(" ")}`,
      );

      const socket = toSocket(client);
      const connection = rpcServer.createWebSocketConnection(socket);

      rpcServer.forward(connection, localConnection);
      console.log("[INFO] Forwarding new client connection");

      socket.onClose((code, reason) => {
        console.log(
          `[INFO] Client connection closed - Code: ${code}, Reason: ${reason}`,
        );
        try {
          localConnection.dispose();
        } catch (error) {
          console.error("[ERROR] Error disposing local connection:", error);
        }
      });
    } catch (error) {
      console.error(
        "[ERROR] Failed to establish language server connection:",
        error,
      );
      client.close();
    }
  });
} catch (error) {
  console.error("[FATAL] Failed to start WebSocket server:", error);
  process.exit(1);
}

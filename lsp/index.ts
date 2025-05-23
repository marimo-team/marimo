import type * as http from "node:http";
import parseArgs from "minimist";
import type ws from "ws";
import { WebSocketServer } from "ws";
import type * as rpc from "@sourcegraph/vscode-ws-jsonrpc";
import * as rpcServer from "@sourcegraph/vscode-ws-jsonrpc/lib/server";
import path from "node:path";
import fs from "node:fs/promises";
import fsSync from "node:fs";

const LOG_FILE = path.join(
  process.env.XDG_CACHE_HOME || path.join(process.env.HOME || "", ".cache"),
  "marimo",
  "logs",
  "github-copilot-lsp.log",
);

let logFileCreated = false;

const appendToFileLog = async (...args: any[]) => {
  const log = args.join(" ");
  if (!logFileCreated) {
    await fs.mkdir(path.dirname(LOG_FILE), { recursive: true });
    // Clear file on startup
    await fs.writeFile(LOG_FILE, "");
    logFileCreated = true;
  }
  await fs.appendFile(LOG_FILE, `${log}\n`);
};

const Logger = {
  debug: (...args: any[]) => {
    console.log(...args);
    void appendToFileLog("[DEBUG]", ...args);
  },
  log: (...args: any[]) => {
    console.log(...args);
    void appendToFileLog("[INFO]", ...args);
  },
  error: (...args: any[]) => {
    console.error(...args);
    void appendToFileLog("[ERROR]", ...args);
  },
};

// Adapted from https://github.com/wylieconlon/jsonrpc-ws-proxy
const COPILOT_LSP_PATH = path.join(
  __dirname,
  "copilot",
  "dist",
  "language-server.js",
);
if (!fsSync.existsSync(COPILOT_LSP_PATH)) {
  Logger.error("Compilation artifact does not exist. Exiting.");
  process.exit(1);
}

const argv = parseArgs(process.argv.slice(2));

if (argv.help) {
  Logger.log("Usage: index.js --port 3000");
  process.exit(0);
}

const serverPort: number = Number.parseInt(argv.port) || 3000;

const languageServers: Record<string, string[]> = {
  copilot: ["node", COPILOT_LSP_PATH, "--stdio"],
};

function toSocket(webSocket: ws): rpc.IWebSocket {
  return {
    send: (content) => {
      try {
        webSocket.send(content);
      } catch (error) {
        Logger.error("Failed to send message:", error);
      }
    },
    onMessage: (cb) => {
      webSocket.onmessage = (event) => {
        try {
          Logger.debug("Received message:", event.data);
          cb(event.data);
        } catch (error) {
          Logger.error("Error processing message:", error);
        }
      };
    },
    onError: (cb) => {
      webSocket.onerror = (event) => {
        Logger.error("WebSocket error:", event);
        if ("message" in event) {
          cb(event.message);
        }
      };
    },
    onClose: (cb) => {
      webSocket.onclose = (event) => {
        Logger.log(
          `WebSocket closed with code ${event.code}, reason: ${event.reason}`,
        );
        cb(event.code, event.reason);
      };
    },
    dispose: () => {
      try {
        webSocket.close();
      } catch (error) {
        Logger.error("Error closing WebSocket:", error);
      }
    },
  };
}

async function verifyCopilotLSP() {
  if (!fsSync.existsSync(COPILOT_LSP_PATH)) {
    Logger.error(
      `Copilot LSP not found at ${COPILOT_LSP_PATH}. Likely a build error or missing dependencies.`,
    );
    process.exit(1);
  }
}

// Add error handling for WebSocket server creation
try {
  const wss = new WebSocketServer(
    {
      port: serverPort,
      perMessageDeflate: false,
    },
    () => {
      Logger.log(`WebSocket server listening on port ${serverPort}`);
    },
  );

  wss.on("error", (error) => {
    Logger.error("WebSocket server error:", error);
  });

  wss.on("connection", (client: ws, request: http.IncomingMessage) => {
    Logger.log(`New connection from ${request.socket.remoteAddress}`);

    void verifyCopilotLSP();

    let langServer: string[] | undefined;

    Object.keys(languageServers).forEach((key) => {
      if (request.url === `/${key}`) {
        langServer = languageServers[key];
        Logger.log(`Matched language server: ${key}`);
      }
    });

    if (!langServer || !langServer.length) {
      Logger.error(`Invalid language server requested: ${request.url}`);
      client.close();
      return;
    }

    try {
      const localConnection = rpcServer.createServerProcess(
        "local",
        langServer[0],
        langServer.slice(1),
      );
      Logger.log(`Created language server process: ${langServer.join(" ")}`);

      const socket = toSocket(client);
      const connection = rpcServer.createWebSocketConnection(socket);

      rpcServer.forward(connection, localConnection);
      Logger.log("Forwarding new client connection");

      socket.onClose((code, reason) => {
        Logger.log(
          `Client connection closed - Code: ${code}, Reason: ${reason}`,
        );
        try {
          localConnection.dispose();
        } catch (error) {
          Logger.error("Error disposing local connection:", error);
        }
      });
    } catch (error) {
      Logger.error("Failed to establish language server connection:", error);
      client.close();
    }
  });
} catch (error) {
  Logger.error("[FATAL] Failed to start WebSocket server:", error);
  process.exit(1);
}

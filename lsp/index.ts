import type { IncomingMessage } from "node:http";
import type { IWebSocket } from "@sourcegraph/vscode-ws-jsonrpc";
import { forward } from "@sourcegraph/vscode-ws-jsonrpc/lib/server/connection.js";
import {
  createServerProcess,
  createWebSocketConnection,
} from "@sourcegraph/vscode-ws-jsonrpc/lib/server/launch.js";
import parseArgs from "minimist";
import type { WebSocket } from "ws";
import { WebSocketServer } from "ws";

class WebSocketAdapter implements IWebSocket {
  private webSocket: WebSocket;

  constructor(webSocket: WebSocket) {
    this.webSocket = webSocket;
  }

  send(content: string): void {
    this.webSocket.send(content);
  }

  onMessage(callback: (data: any) => void): void {
    this.webSocket.onmessage = (event: any) => {
      callback(event.data);
    };
  }

  onError(callback: (err: any) => void): void {
    this.webSocket.onerror = (event: any) => {
      if ("message" in event) {
        callback(event.message);
      }
    };
  }

  onClose(callback: (code: number, reason: string) => void): void {
    this.webSocket.onclose = (event: any) => {
      callback(event.code, event.reason);
    };
  }

  dispose(): void {
    this.webSocket.close();
  }
}

function handleWebSocketConnection(
  languageServerCommand: string[],
  webSocket: WebSocket,
  _: IncomingMessage,
) {
  if (!languageServerCommand) {
    webSocket.close();
    return;
  }

  const jsonRpcConnection = createServerProcess(
    languageServerCommand.join(" "),
    languageServerCommand[0],
    languageServerCommand.slice(1),
  );

  const socket = new WebSocketAdapter(webSocket);
  const connection = createWebSocketConnection(socket);
  forward(connection, jsonRpcConnection);

  socket.onClose(() => {
    jsonRpcConnection.dispose();
    connection.dispose();
  });

  connection.onClose(() => {
    jsonRpcConnection.dispose();
    socket.dispose();
  });
}

function startWebSocketServer(
  port: number,
  languageServerCommand: string[],
): void {
  const webSocketServer = new WebSocketServer({
    port,
    perMessageDeflate: false,
  });

  webSocketServer.on("connection", (webSocket, request) =>
    handleWebSocketConnection(languageServerCommand, webSocket, request),
  );
}

async function main(): Promise<void> {
  const argv = parseArgs(process.argv.slice(2));
  const serverPort = Number.parseInt(argv.port) || 3000;
  const languageServerCommand = argv.lsp.split(" ");

  startWebSocketServer(serverPort, languageServerCommand);
}

void main();

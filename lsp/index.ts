import { appendFile, mkdir, writeFile } from "node:fs/promises";
import type { IncomingMessage } from "node:http";
import { dirname } from "node:path";
import type { IWebSocket } from "@sourcegraph/vscode-ws-jsonrpc";
import { forward } from "@sourcegraph/vscode-ws-jsonrpc/lib/server/connection.js";
import {
  createServerProcess,
  createWebSocketConnection,
} from "@sourcegraph/vscode-ws-jsonrpc/lib/server/launch.js";
import parseArgs from "minimist";
import type { CloseEvent, Data, ErrorEvent, MessageEvent, WebSocket } from "ws";
import { WebSocketServer } from "ws";

class Logger {
  private constructor(private readonly logFilePath: string) {
    this.logFilePath = logFilePath;
  }

  static async create(logFilePath: string): Promise<Logger> {
    await mkdir(dirname(logFilePath), { recursive: true });
    await writeFile(logFilePath, "");

    return new Logger(logFilePath);
  }

  private async appendToLogFile(...args: unknown[]): Promise<void> {
    const log = args.join(" ");

    try {
      await appendFile(this.logFilePath, `${log}\n`);
    } catch (error) {
      console.error("Failed to write to log file:", error);
    }
  }

  debug(...args: Parameters<typeof console.log>): void {
    console.log(...args);
    void this.appendToLogFile("[DEBUG]", ...args);
  }

  log(...args: Parameters<typeof console.log>): void {
    console.log(...args);
    void this.appendToLogFile("[INFO]", ...args);
  }

  error(...args: Parameters<typeof console.error>): void {
    console.error(...args);
    void this.appendToLogFile("[ERROR]", ...args);
  }
}

class WebSocketAdapter implements IWebSocket {
  constructor(
    private readonly webSocket: WebSocket,
    private readonly logger: Logger,
  ) {
    this.webSocket = webSocket;
    this.logger = logger;
  }

  send(content: string): void {
    try {
      this.webSocket.send(content);
    } catch (error) {
      this.logger.error("Failed to send message:", error);
    }
  }

  onMessage(callback: (data: Data) => void): void {
    this.webSocket.onmessage = (event: MessageEvent) => {
      try {
        this.logger.debug("Received message:", event.data);
        callback(event.data);
      } catch (error) {
        this.logger.error("Error handling message:", error);
      }
    };
  }

  onError(callback: (message: string) => void): void {
    this.webSocket.onerror = (event: ErrorEvent) => {
      this.logger.error("WebSocket error:", event);
      if ("message" in event) {
        callback(event.message);
      }
    };
  }

  onClose(callback: (code: number, reason: string) => void): void {
    this.webSocket.onclose = (event: CloseEvent) => {
      this.logger.log(
        `WebSocket closed with code ${event.code}: ${event.reason}`,
      );

      callback(event.code, event.reason);
    };
  }

  dispose(): void {
    this.webSocket.close();
  }
}

function handleWebSocketConnection(
  languageServerCommand: string[],
  logger: Logger,
  webSocket: WebSocket,
  _: IncomingMessage,
): void {
  if (!languageServerCommand) {
    webSocket.close();
    return;
  }

  const jsonRpcConnection = createServerProcess(
    languageServerCommand.join(" "),
    languageServerCommand[0],
    languageServerCommand.slice(1),
  );

  const socket = new WebSocketAdapter(webSocket, logger);
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
  logger: Logger,
): void {
  const webSocketServer = new WebSocketServer({
    port,
    perMessageDeflate: false,
  });

  webSocketServer.on("error", (error) => {
    logger.error("WebSocket server error:", error);
  });

  webSocketServer.on("connection", (webSocket, request) => {
    logger.log(`New connection from ${request.socket.remoteAddress}`);
    try {
      handleWebSocketConnection(
        languageServerCommand,
        logger,
        webSocket,
        request,
      );
    } catch (error) {
      logger.error("Failed to start WebSocket bridge:", error);
      webSocket.close();
    }
  });
}

async function main(): Promise<void> {
  const argv = parseArgs(process.argv);

  if (argv.help) {
    console.log(
      'Usage: node index.cjs --log-file <path> --lsp "<command>" [--port <port>]',
    );

    return;
  }

  const logger = await Logger.create(argv["log-file"]);
  const serverPort = Number.parseInt(argv.port) || 3000;
  const languageServerCommand = argv.lsp.split(" ");

  startWebSocketServer(serverPort, languageServerCommand, logger);
}

void main();

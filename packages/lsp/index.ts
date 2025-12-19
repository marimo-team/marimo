import { appendFile, mkdir, writeFile } from "node:fs/promises";
import type { IncomingMessage } from "node:http";
import { dirname } from "node:path";
import parseArgs from "minimist";
import type { IWebSocket } from "vscode-ws-jsonrpc";
import {
  createServerProcess,
  createWebSocketConnection,
  forward,
} from "vscode-ws-jsonrpc/server";
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
      // biome-ignore lint/suspicious/noConsole: For printing to the console
      console.error("Failed to write to log file:", error);
    }
  }

  debug(...args: Parameters<typeof console.log>): void {
    // biome-ignore lint/suspicious/noConsole: For printing to the console
    console.log(...args);
    void this.appendToLogFile("[DEBUG]", ...args);
  }

  log(...args: Parameters<typeof console.log>): void {
    // biome-ignore lint/suspicious/noConsole: For printing to the console
    console.log(...args);
    void this.appendToLogFile("[INFO]", ...args);
  }

  error(...args: Parameters<typeof console.error>): void {
    // biome-ignore lint/suspicious/noConsole: For printing to the console
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
      this.logger.debug("Sent message:", content);
    } catch (error) {
      this.logger.error("Failed to send message:", error);
    }
  }

  onMessage(callback: (data: Data) => void): void {
    this.webSocket.onmessage = (event: MessageEvent) => {
      try {
        callback(event.data);
        this.logger.debug("Received message:", event.data);
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

export function parseTypedCommand(typedCommand: string): string[] {
  if (!typedCommand.includes(":")) {
    // Fallback for old format - simple split by spaces
    return typedCommand.split(" ");
  }

  const colonIndex = typedCommand.indexOf(":");
  const serverType = typedCommand.substring(0, colonIndex);
  const binaryPath = typedCommand.substring(colonIndex + 1);

  switch (serverType) {
    case "copilot":
      return ["node", binaryPath, "--stdio"];
    case "basedpyright":
      return [binaryPath, "--stdio"];
    case "pyrefly":
      return [binaryPath, "lsp"];
    case "ty":
      return [binaryPath, "server"];
    default:
      throw new Error(`Unknown LSP server type: ${serverType}`);
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

  if (!jsonRpcConnection) {
    throw new Error("Not able to create json-rpc connection.");
  }

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
    // biome-ignore lint/suspicious/noConsole: For printing to the console
    console.log(
      'Usage: node index.cjs --log-file <path> --lsp "<command>" [--port <port>]',
    );

    return;
  }

  const logFile = argv["log-file"] || "/tmp/lsp-server.log";
  const logger = await Logger.create(logFile);
  const serverPort = Number.parseInt(argv.port, 10) || 3000;
  const languageServerCommand = parseTypedCommand(argv.lsp || "echo test");

  logger.log(`Parsed LSP command: ${languageServerCommand.join(" ")}`);
  startWebSocketServer(serverPort, languageServerCommand, logger);
}

void main();

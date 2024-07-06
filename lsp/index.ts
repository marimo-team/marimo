import * as http from "http";
import parseArgs from "minimist";
import ws, { WebSocketServer } from "ws";
import * as rpc from "@sourcegraph/vscode-ws-jsonrpc";
import * as rpcServer from "@sourcegraph/vscode-ws-jsonrpc/lib/server";
import path from "path";

// Adapted from https://github.com/wylieconlon/jsonrpc-ws-proxy

let argv = parseArgs(process.argv.slice(2));

if (argv.help) {
  console.log(`Usage: index.js --port 3000`);
  process.exit(1);
}

let serverPort: number = parseInt(argv.port) || 3000;

let languageServers: Record<string, string[]> = {
  copilot: [
    "node",
    path.join(__dirname, "copilot", "dist", "language-server.js"),
  ],
};

const wss = new WebSocketServer(
  {
    port: serverPort,
    perMessageDeflate: false,
  },
  () => {
    console.log(`Listening to http and ws requests on ${serverPort}`);
  },
);

function toSocket(webSocket: ws): rpc.IWebSocket {
  return {
    send: (content) => webSocket.send(content),
    onMessage: (cb) => (webSocket.onmessage = (event) => cb(event.data)),
    onError: (cb) =>
      (webSocket.onerror = (event) => {
        if ("message" in event) {
          cb(event.message);
        }
      }),
    onClose: (cb) =>
      (webSocket.onclose = (event) => cb(event.code, event.reason)),
    dispose: () => webSocket.close(),
  };
}

wss.on("connection", (client: ws, request: http.IncomingMessage) => {
  let langServer: string[] | undefined;

  Object.keys(languageServers).forEach((key) => {
    if (request.url === "/" + key) {
      langServer = languageServers[key];
    }
  });

  if (!langServer || !langServer.length) {
    console.error("Invalid language server", request.url);
    client.close();
    return;
  }

  const localConnection = rpcServer.createServerProcess(
    "local",
    langServer[0],
    langServer.slice(1),
  );
  const socket = toSocket(client);
  const connection = rpcServer.createWebSocketConnection(socket);

  rpcServer.forward(connection, localConnection);
  console.log(`Forwarding new client`);

  socket.onClose((code, reason) => {
    console.log("Client closed", reason);
    localConnection.dispose();
  });
});

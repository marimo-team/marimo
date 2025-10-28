import { newMessagePortRpcSession, RpcTarget } from "capnweb";
import { createContext, useContext } from "react";
import type { InitializationCommand, NotebookControls, NotebookControlsHandler, NotebookControlsKey, NotebookHostControls, NotebookHostControlsStub, RequestConnectionCommand } from "./notebook-controls";

export interface NotebookFileStoreControls {
  saveNotebook: (contents: string) => Promise<void>;
  readNotebook: () => Promise<string | null>;
  saveNotebookPreview: (base64Image: string) => Promise<void>;
};

export interface NotebookRpcServer extends NotebookControls {
  listen: () => void;
  close: () => void;
  waitForFsReady: () => Promise<void>;
  registerHandler: <K extends NotebookControlsKey>(key: K, handler: NotebookControlsHandler<K>) => void;
  getFilestore: () => NotebookFileStoreControls;
}


export class NotebookRpc extends RpcTarget implements NotebookRpcServer {
  private allowedDomains: string[];
  private handlers: { [K in NotebookControlsKey]?: NotebookControlsHandler<K> };
  private hostControls: NotebookHostControlsStub | undefined;
  private connections: Record<string, MessageChannel>;
  private handleRequestConnectionBound: (event: MessageEvent<any>) => void;
  private fsReadyPromise: Promise<void>;
  private fsReadyResolve!: () => void;

  constructor(allowedDomains: string[]) {
    super();
    this.allowedDomains = allowedDomains;
    this.handlers = {};
    this.connections = {};
    this.handleRequestConnectionBound = this.handleRequestConnection.bind(this);

    this.fsReadyPromise = new Promise((resolve, reject) => {
      const timeoutFunction = () => {
        reject(new Error("Timeout waiting for notebook host to connect"));
      };
      const timeout = setTimeout(timeoutFunction, 60000);
      this.fsReadyResolve = () => {
        clearTimeout(timeout);
        resolve();
      };
    });
  }

  /**
   * Listen for connections attempts from the parent window and send back the MessagePort
   * to communicate with the parent.
   */
  listen() {
    window.addEventListener("message", this.handleRequestConnectionBound);
  }

  close() {
    window.removeEventListener("message", this.handleRequestConnectionBound);

    Object.values(this.connections).forEach((channel) => {
      channel.port1.close();
    });
    this.connections = {};
  }

  async waitForFsReady() {
    return this.fsReadyPromise;
  }

  private handleRequestConnection(event: MessageEvent<any>) {
    if (!this.isOriginAllowedDomain(event.origin)) {
      console.warn(`Ignoring message from invalid origin: ${event.origin}`);
      return;
    }
    const command = event.data?.command || "";
    if (typeof command !== "string" || command !== "requestConnection") {
      return;
    }

    const reqCommand = event.data as RequestConnectionCommand;

    if (!reqCommand.id) {
      console.error("No id provided in requestConnection command");
      return;
    }

    const notebookServerChannel = new MessageChannel();
    const hostServerChannel = new MessageChannel();
    this.connections[reqCommand.id] = notebookServerChannel;

    newMessagePortRpcSession(notebookServerChannel.port1, this);

    const stub = newMessagePortRpcSession<NotebookHostControls>(hostServerChannel.port1);
    this.hostControls = stub;
    this.fsReadyResolve();

    // Send postMesage to the parent to establish the connection
    const init: InitializationCommand = {
      command: "initialize",
      id: reqCommand.id,
      sendPort: notebookServerChannel.port2,
      recvPort: hostServerChannel.port2,
    };
    window.parent.postMessage(init, event.origin, [notebookServerChannel.port2, hostServerChannel.port2]);
  }

  private isOriginAllowedDomain(origin: string): boolean {
    // If the origin is localhost, always allow it
    if (origin.includes("localhost") || origin.includes("127.0.0.1")) {
      return true;
    }
    const domain = new URL(origin).hostname;
    return this.allowedDomains.includes(domain);
  }

  // We allow late registration of handlers so we can use different handlers
  // in the notebook application
  private getHandler<K extends NotebookControlsKey>(key: K): NotebookControlsHandler<K> {
    const handler = this.handlers[key];
    if (!handler) {
      throw new Error(`No handler registered for ${key}`);
    }
    return handler;
  }

  async createCell(code: string): Promise<void> {
    const handler = this.getHandler("createCell");
    handler(code);
  }

  async triggerAlert(message: string): Promise<void> {
    const handler = this.getHandler("triggerAlert");
    handler(message);
  }

  async captureNotebookPreview(): Promise<string | null> {
    const handler = this.getHandler("captureNotebookPreview");
    return handler();
  }

  registerHandler<K extends NotebookControlsKey>(key: K, handler: NotebookControlsHandler<K>) {
    this.handlers[key] = handler;
  }

  getFilestore(): NotebookFileStoreControls {
    if(!this.hostControls) {
      throw new Error("No filestore registered");
    }
    return this.hostControls;
  }
}

export class DummyNotebookRpc implements NotebookRpcServer {
  async createCell(code: string): Promise<void> {
    console.warn("DummyNotebookRpc: createCell called with code:", code);
  }
  async triggerAlert(message: string): Promise<void> {
    alert(`DummyNotebookRpc: ${message}`);
  }
  async captureNotebookPreview(): Promise<string | null> {
    console.warn("DummyNotebookRpc: captureNotebookPreview called");
    return null;
  }
  listen(): void {
    console.warn("DummyNotebookRpc: listen called");
  }
  close(): void {
    console.warn("DummyNotebookRpc: close called");
  }
  waitForFsReady(): Promise<void> {
    console.warn("DummyNotebookRpc: waitForFsReady called");
    return Promise.resolve();
  }

  registerHandler<K extends NotebookControlsKey>(key: K, _handler: NotebookControlsHandler<K>): void {
    console.warn(`DummyNotebookRpc: registerHandler called for key ${key}`);
  }

  getFilestore(): NotebookFileStoreControls {
    return {
      saveNotebook: async (_contents: string) => {
        console.warn("DummyNotebookRpc: saveNotebook called");
      },
      readNotebook: async () => {
        console.warn("DummyNotebookRpc: readNotebook called");
        return null;
      },
      saveNotebookPreview: async (_base64Image: string) => {
        console.warn("DummyNotebookRpc: saveNotebookPreview called");
      }
    }
  }
}


const NotebookRpcServerContext = createContext<NotebookRpcServer | undefined>(undefined);

export type NotebookRpcServerProviderProps = {
  notebookRpcServer: NotebookRpcServer;
} & React.PropsWithChildren;

export const NotebookRpcServerProvider: React.FC<NotebookRpcServerProviderProps> = ({
  notebookRpcServer,
  children,
}) => {
  return (
    <NotebookRpcServerContext.Provider value={notebookRpcServer}>
      {children}
    </NotebookRpcServerContext.Provider>
  );
};

/**
 * useIframeRpc
 */
export function useNotebookRpcServer(): NotebookRpcServer {
  const ctx = useContext(NotebookRpcServerContext);
  if (!ctx) {
    throw new Error("useNotebookRpc must be used within a NotebookRpcProvider");
  }
  return ctx;
}

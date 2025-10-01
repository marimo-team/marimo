import type { FileStore } from "@/core/wasm/store";
import type { NotebookRpcServer } from "./notebook-rpc";


export class PostMessageFileStore implements FileStore {
  private notebookRpc: NotebookRpcServer;

  constructor(notebookRpc: NotebookRpcServer) {
    this.notebookRpc = notebookRpc;
  }

  async saveFile(contents: string): Promise<void> {
    return this.notebookRpc.getFilestore().saveNotebook(contents);
  }

  async readFile(): Promise<string | null> {
    return this.notebookRpc.getFilestore().readNotebook();
  }
}
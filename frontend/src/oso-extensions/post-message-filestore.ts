import type { FileStore } from "@/core/wasm/store";
import type { NotebookRpcServer } from "./notebook-rpc";

type CapturePreview = () => Promise<string | null>;

export class PostMessageFileStore implements FileStore {
  private notebookRpc: NotebookRpcServer;
  private capturePreview: CapturePreview | null = null;

  constructor(notebookRpc: NotebookRpcServer, capturePreview?: CapturePreview) {
    this.notebookRpc = notebookRpc;
    this.capturePreview = capturePreview ?? null;
  }

  setCapturePreview(capturePreview: CapturePreview | null): void {
    this.capturePreview = capturePreview;
  }

  async saveFile(contents: string): Promise<void> {
    await this.notebookRpc.getFilestore().saveNotebook(contents);

    if (this.capturePreview) {
      try {
        const preview = await this.capturePreview();
        if (preview) {
          await this.notebookRpc.getFilestore().saveNotebookPreview(preview);
        }
      } catch (error) {
        console.error("Failed to save preview:", error);
      }
    }
  }

  async readFile(): Promise<string | null> {
    return this.notebookRpc.getFilestore().readNotebook();
  }
}

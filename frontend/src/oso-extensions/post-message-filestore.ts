import type { FileStore } from "@/core/wasm/store";
import type { NotebookRpcServer } from "./notebook-rpc";

type CapturePreview = () => Promise<string | null>;
type ConfirmSave = () => void;

export class PostMessageFileStore implements FileStore {
  private notebookRpc: NotebookRpcServer;
  private capturePreview: CapturePreview | null = null;
  private confirmSave: ConfirmSave | null = null;

  constructor(notebookRpc: NotebookRpcServer) {
    this.notebookRpc = notebookRpc;
  }

  setCapturePreview(capturePreview: CapturePreview | null, confirmSave?: ConfirmSave | null): void {
    this.capturePreview = capturePreview;
    this.confirmSave = confirmSave ?? null;
  }

  async saveFile(contents: string): Promise<void> {
    await this.notebookRpc.getFilestore().saveNotebook(contents);

    if (this.capturePreview) {
      try {
        const preview = await this.capturePreview();
        if (preview) {
          await this.notebookRpc.getFilestore().saveNotebookPreview(preview);
          this.confirmSave?.();
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

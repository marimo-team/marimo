import type { RpcStub } from "capnweb";

export interface NotebookHostControls {
  // Save the contents of a notebook via the host
  saveNotebook: (contents: string) => Promise<void>;
  // Read the contents of a notebook via the host
  readNotebook: () => Promise<string | null>;
  // Save a preview image of the notebook when it changes
  saveNotebookPreview: (base64Image: string) => Promise<void>;
}

export interface NotebookControls {
  createCell: (code: string) => Promise<void>;

  triggerAlert: (message: string) => Promise<void>;

  captureNotebookPreview: () => Promise<string | null>;
}

export type NotebookControlsStub = RpcStub<NotebookControls>;

export type NotebookHostControlsStub = RpcStub<NotebookHostControls>;

export type NotebookControlsKey = keyof Omit<
  NotebookControls,
  "registerNotebookFilestore"
>;
export type NotebookControlsHandler<K extends NotebookControlsKey> =
  NotebookControls[K];

export type InitializationCommand = {
  command: "initialize";
  id: string;
  sendPort: MessagePort;
  recvPort: MessagePort;
};

export type RequestConnectionCommand = {
  command: "requestConnection";
  id: string;
};

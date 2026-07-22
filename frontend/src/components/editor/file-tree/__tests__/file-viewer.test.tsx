/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import type { FileDetailsResponse, FileInfo } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { FileViewer, MAX_FILE_PREVIEW_BYTES } from "../file-viewer";

vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: ({
    value,
    onChange,
  }: {
    value?: string;
    onChange?: (value: string) => void;
  }) => (
    <textarea
      data-testid="code-editor"
      value={value ?? ""}
      onChange={(evt) => onChange?.(evt.target.value)}
    />
  ),
}));

vi.mock("@/core/wasm/utils", () => ({ isWasm: () => false }));

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>
    <TooltipProvider>{children}</TooltipProvider>
  </Provider>
);

const file: FileInfo = {
  id: "/workspace/installer.dmg",
  path: "/workspace/installer.dmg",
  name: "installer.dmg",
  isDirectory: false,
  isMarimoFile: false,
  size: 20 * 1024 * 1024,
};

function renderViewer(response: FileDetailsResponse) {
  const client = MockRequestClient.create({
    sendFileDetails: vi.fn().mockResolvedValue(response),
  });
  store.set(requestClientAtom, client);
  render(<FileViewer file={file} onOpenNotebook={vi.fn()} />, { wrapper });
  return client;
}

describe("FileViewer bounded previews", () => {
  beforeEach(() => {
    store.set(requestClientAtom, null);
  });

  it("requests a bounded preview and shows oversized metadata", async () => {
    const client = renderViewer({
      file,
      contents: null,
      mimeType: "application/x-apple-diskimage",
      isBase64: false,
      isTooLarge: true,
    });

    expect(await screen.findByText(/too large to preview/i)).toBeVisible();
    expect(screen.getByText("20 MB")).toBeVisible();
    expect(screen.getByRole("button", { name: /download/i })).toBeVisible();
    expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
    expect(client.sendFileDetails).toHaveBeenCalledWith({
      path: file.path,
      maxBytes: MAX_FILE_PREVIEW_BYTES,
    });
  });

  it("shows unsupported metadata with a download action, not base64 text", async () => {
    renderViewer({
      file: { ...file, size: 4 },
      contents: "AAEC",
      mimeType: "application/x-apple-diskimage",
      isBase64: true,
      isTooLarge: false,
    });

    expect(await screen.findByText(/cannot be previewed/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /download/i })).toBeVisible();
    expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
  });

  it("continues to render small text files", async () => {
    renderViewer({
      file: { ...file, name: "notes.txt", size: 5 },
      contents: "hello",
      mimeType: "text/plain",
      isBase64: false,
      isTooLarge: false,
    });

    await waitFor(() => {
      expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    });
    expect(screen.queryByText(/too large to preview/i)).not.toBeInTheDocument();
  });

  it("preserves edits to an initially empty text file across remount", async () => {
    const emptyFile: FileInfo = {
      id: "/workspace/empty.txt",
      path: "/workspace/empty.txt",
      name: "empty.txt",
      isDirectory: false,
      isMarimoFile: false,
      size: 0,
    };
    const response: FileDetailsResponse = {
      file: emptyFile,
      contents: "",
      mimeType: "text/plain",
      isBase64: false,
      isTooLarge: false,
    };
    const client = MockRequestClient.create({
      sendFileDetails: vi.fn().mockResolvedValue(response),
    });
    store.set(requestClientAtom, client);

    const { unmount } = render(
      <FileViewer file={emptyFile} onOpenNotebook={vi.fn()} />,
      { wrapper },
    );

    const editor =
      await screen.findByTestId<HTMLTextAreaElement>("code-editor");
    fireEvent.change(editor, { target: { value: "draft" } });
    unmount();

    render(<FileViewer file={emptyFile} onOpenNotebook={vi.fn()} />, {
      wrapper,
    });

    const reopened =
      await screen.findByTestId<HTMLTextAreaElement>("code-editor");
    await waitFor(() => {
      expect(reopened.value).toBe("draft");
    });
  });
});

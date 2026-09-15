/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DownloadStorage } from "@/core/storage/request-registry";
import { StorageFileViewer } from "../storage-file-viewer";

vi.mock("@/components/editor/cell/useAddCell", () => ({
  useAddCodeToNewCell: () => vi.fn(),
}));

vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: ({
    value,
    language,
    readOnly,
  }: {
    value?: string;
    language?: string;
    readOnly?: boolean;
  }) => (
    <textarea
      data-testid="code-editor"
      data-language={language}
      value={value}
      readOnly={readOnly}
    />
  ),
}));

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

describe("StorageFileViewer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders TOML from generic storage metadata as read-only TOML", async () => {
    const request = vi.spyOn(DownloadStorage, "request").mockResolvedValue({
      request_id: "request-id",
      url: "https://example.com/pyproject.toml?signature=secret",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => '[project]\nname = "demo"',
      }),
    );

    render(
      <TooltipProvider>
        <StorageFileViewer
          entry={{
            path: "config/pyproject.toml",
            kind: "file",
            size: 24,
            lastModified: null,
            mimeType: null,
          }}
          namespace="files"
          protocol="s3"
          backendType="fsspec"
          onBack={vi.fn()}
        />
      </TooltipProvider>,
    );

    const editor =
      await screen.findByTestId<HTMLTextAreaElement>("code-editor");
    expect(editor).toHaveAttribute("data-language", "toml");
    expect(editor).toHaveAttribute("readonly");
    expect(editor).toHaveValue('[project]\nname = "demo"');
    expect(request).toHaveBeenCalledWith({
      namespace: "files",
      path: "config/pyproject.toml",
      preview: true,
    });
  });
});

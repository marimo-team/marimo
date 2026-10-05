/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { ExportedFile } from "@/core/network/types";
import { exportNotebook } from "../export-notebook";
import { DEFAULT_EXPORT_OPTIONS, type ExportOptions } from "../state";

type Requests = Parameters<typeof exportNotebook>[0]["requests"];

const FILE: ExportedFile<string> = {
  contents: "exported",
  filename: "notebook.txt",
  mediaType: "text/plain",
};

function makeOptions(overrides: Partial<ExportOptions> = {}): ExportOptions {
  return {
    ...DEFAULT_EXPORT_OPTIONS,
    ...overrides,
  };
}

function makeRequests(): Requests {
  return {
    exportAsHTML: vi.fn().mockResolvedValue(FILE),
    exportAsMarkdown: vi.fn().mockResolvedValue(FILE),
    exportAsIPYNB: vi.fn().mockResolvedValue(FILE),
    exportAsPDF: vi.fn().mockResolvedValue({
      ...FILE,
      contents: new Blob(),
      filename: "notebook.pdf",
      mediaType: "application/pdf",
    }),
    exportAsScript: vi.fn().mockResolvedValue(FILE),
    readCode: vi.fn().mockResolvedValue({
      contents: "import marimo",
    }),
  };
}

describe("exportNotebook", () => {
  let requests: Requests;
  let captureOutputs: Mock<() => Promise<void>>;
  let capturePNG: Mock<() => Promise<void>>;
  let downloadFile: Mock<(file: ExportedFile) => void>;
  let getLayout: Mock;

  beforeEach(() => {
    requests = makeRequests();
    captureOutputs = vi.fn().mockResolvedValue(undefined);
    capturePNG = vi.fn().mockResolvedValue(undefined);
    downloadFile = vi.fn();
    getLayout = vi.fn().mockResolvedValue({
      type: "slides",
      data: { deck: { transition: "fade" } },
    });
  });

  const run = (
    format: Parameters<typeof exportNotebook>[0]["format"],
    options = makeOptions(),
  ) =>
    exportNotebook({
      format,
      options,
      requests,
      sourceFilename: "notebook.py",
      htmlFiles: ["data.csv"],
      getLayout,
      captureOutputs,
      capturePNG,
      downloadFile,
    });

  it("passes HTML settings and virtual files through the session API", async () => {
    await run("html", makeOptions({ html: { includeCode: false } }));

    expect(requests.exportAsHTML).toHaveBeenCalledWith({
      download: false,
      files: ["data.csv"],
      includeCode: false,
      layout: { type: "slides", data: { deck: { transition: "fade" } } },
    });
    expect(downloadFile).toHaveBeenCalledWith(FILE);
    expect(getLayout).toHaveBeenCalledOnce();
  });

  it("passes the selected Markdown flavor through the session API", async () => {
    await run("markdown", makeOptions({ markdown: { flavor: "qmd" } }));

    expect(requests.exportAsMarkdown).toHaveBeenCalledWith({
      download: false,
      flavor: "qmd",
    });
    expect(getLayout).not.toHaveBeenCalled();
    expect(downloadFile).toHaveBeenCalledWith(FILE);
  });

  it("captures outputs before an IPYNB export when requested", async () => {
    const calls: string[] = [];
    captureOutputs.mockImplementation(async () => {
      calls.push("capture");
    });
    vi.mocked(requests.exportAsIPYNB).mockImplementation(async () => {
      calls.push("export");
      return FILE;
    });

    await run(
      "ipynb",
      makeOptions({
        ipynb: { sortMode: "top-down", includeOutputs: true },
      }),
    );

    expect(calls).toEqual(["capture", "export"]);
    expect(requests.exportAsIPYNB).toHaveBeenCalledWith({
      download: false,
      sortMode: "top-down",
      includeOutputs: true,
    });
    expect(downloadFile).toHaveBeenCalledWith(FILE);
  });

  it("skips browser capture when IPYNB outputs are excluded", async () => {
    await run("ipynb");

    expect(captureOutputs).not.toHaveBeenCalled();
    expect(requests.exportAsIPYNB).toHaveBeenCalledWith({
      download: false,
      sortMode: "topological",
      includeOutputs: false,
    });
    expect(downloadFile).toHaveBeenCalledWith(FILE);
  });

  it("captures current outputs before PDF export and sends every option", async () => {
    const pdf = makeOptions({
      pdf: {
        preset: "slides",
        includeInputs: false,
        includeOutputs: true,
        webpdf: false,
      },
    });

    await run("pdf", pdf);

    expect(captureOutputs).toHaveBeenCalledOnce();
    expect(requests.exportAsPDF).toHaveBeenCalledWith(pdf.pdf);
    expect(downloadFile).toHaveBeenCalledWith(
      expect.objectContaining({ filename: "notebook.pdf" }),
    );
  });

  it("downloads the editable notebook source", async () => {
    await run("script");

    expect(requests.readCode).toHaveBeenCalledOnce();
    expect(requests.exportAsScript).not.toHaveBeenCalled();
    expect(downloadFile).toHaveBeenCalledWith({
      contents: "import marimo",
      filename: "notebook.py",
      mediaType: "text/plain",
    });
  });

  it("downloads a flat script through the export API", async () => {
    await run(
      "script",
      makeOptions({
        script: { type: "flat" },
      }),
    );

    expect(requests.exportAsScript).toHaveBeenCalledWith({ download: false });
    expect(requests.readCode).not.toHaveBeenCalled();
    expect(downloadFile).toHaveBeenCalledWith(FILE);
  });

  it("uses client-side capture for PNG", async () => {
    await run("png");

    expect(capturePNG).toHaveBeenCalledOnce();
    expect(downloadFile).not.toHaveBeenCalled();
  });
});

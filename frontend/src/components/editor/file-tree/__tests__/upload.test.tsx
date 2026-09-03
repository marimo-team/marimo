/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type { FileCreateInput, FileCreateResponse } from "@/core/network/types";
import type { FilePath } from "@/utils/paths";
import {
  FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE,
  FILE_EXPLORER_ROOT_ID_ATTRIBUTE,
  getUploadDestinationFromTarget,
  getUploadRootIdFromTarget,
  resolveUploadDirectoryPath,
  uploadFilesToDestination,
} from "../upload";

const filePath = (path: string) => path as FilePath;

describe("resolveUploadDirectoryPath", () => {
  it("uploads an individual file to the explicit destination", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("./sales.csv"),
      }),
    ).toBe("/workspace/data");
  });

  it("preserves a dropped folder's relative structure", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("raw/2026/sales.csv"),
      }),
    ).toBe("/workspace/data/raw/2026");
  });

  it("normalizes relative paths for a Windows destination", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("C:\\workspace\\data"),
        filePath: filePath("raw/2026/sales.csv"),
      }),
    ).toBe("C:\\workspace\\data\\raw\\2026");
  });

  it("normalizes mixed separators in relative paths", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("raw\\2026/sales.csv"),
      }),
    ).toBe("/workspace/data/raw/2026");
  });

  it("removes current-directory components", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("raw/./2026/sales.csv"),
      }),
    ).toBe("/workspace/data/raw/2026");
  });

  it.each(["../sales.csv", "raw/../../sales.csv", "raw\\..\\sales.csv"])(
    "rejects parent traversal in %s",
    (unsafePath) => {
      expect(() =>
        resolveUploadDirectoryPath({
          destinationPath: filePath("/workspace/data"),
          filePath: filePath(unsafePath),
        }),
      ).toThrow(/parent traversal/);
    },
  );

  it.each([
    "C:\\Users\\sales.csv",
    "\\\\server\\share\\sales.csv",
    "file://workspace/sales.csv",
    "/Users/example/sales.csv",
  ])("rejects absolute path %s", (absolutePath) => {
    expect(() =>
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath(absolutePath),
      }),
    ).toThrow(/must be relative/);
  });
});

describe("getUploadDestinationFromTarget", () => {
  it("uses the closest folder as the drop destination", () => {
    const folder = document.createElement("div");
    folder.setAttribute(
      FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE,
      "/workspace/data",
    );
    const child = document.createElement("span");
    folder.append(child);

    expect(getUploadDestinationFromTarget(child, filePath("/workspace"))).toBe(
      "/workspace/data",
    );
  });

  it("preserves the selected root occurrence", () => {
    const folder = document.createElement("div");
    folder.setAttribute(FILE_EXPLORER_ROOT_ID_ATTRIBUTE, "external-root");
    const child = document.createElement("span");
    folder.append(child);

    expect(getUploadRootIdFromTarget(child)).toBe("external-root");
    expect(getUploadRootIdFromTarget(document.createElement("div"))).toBeNull();
  });

  it("uses the workspace root outside a folder", () => {
    expect(
      getUploadDestinationFromTarget(
        document.createElement("div"),
        filePath("/workspace"),
      ),
    ).toBe("/workspace");
  });
});

describe("uploadFilesToDestination", () => {
  it("sends files to the destination and separates server failures", async () => {
    const successfulFile = new File(["success"], "success.txt");
    const failedFile = new File(["failure"], "failure.txt");
    Object.defineProperty(successfulFile, "path", {
      value: "nested/success.txt",
    });
    const createFile = vi.fn(
      async (request: FileCreateInput): Promise<FileCreateResponse> =>
        request.name === "success.txt"
          ? { success: true }
          : { success: false, message: "Permission denied" },
    );
    const onFileProcessed = vi.fn();

    const result = await uploadFilesToDestination({
      files: [successfulFile, failedFile],
      destinationPath: filePath("/workspace/data"),
      createFile,
      onFileProcessed,
    });

    expect(createFile.mock.calls.map(([request]) => request)).toEqual([
      {
        path: "/workspace/data/nested",
        type: "file",
        name: "success.txt",
        file: successfulFile,
      },
      {
        path: "/workspace/data",
        type: "file",
        name: "failure.txt",
        file: failedFile,
      },
    ]);
    expect(result).toEqual({
      successful: [{ file: successfulFile, response: { success: true } }],
      failed: [
        {
          file: failedFile,
          response: { success: false, message: "Permission denied" },
        },
      ],
    });
    expect(onFileProcessed).toHaveBeenCalledTimes(2);
  });

  it("treats a browser-style leading slash as a relative drop path", async () => {
    const browserFile = new File(["data"], "sales.csv");
    Object.defineProperty(browserFile, "path", {
      value: "/raw/2026/sales.csv",
    });
    const createFile = vi
      .fn<(request: FileCreateInput) => Promise<FileCreateResponse>>()
      .mockResolvedValue({ success: true });

    await uploadFilesToDestination({
      files: [browserFile],
      destinationPath: filePath("/workspace/data"),
      createFile,
    });

    expect(createFile).toHaveBeenCalledWith({
      path: "/workspace/data/raw/2026",
      type: "file",
      name: "sales.csv",
      file: browserFile,
    });
  });

  it("waits for every file and normalizes thrown request errors", async () => {
    const failedFile = new File(["failure"], "failure.txt");
    const slowFile = new File(["success"], "slow.txt");
    let finishSlowUpload: ((response: FileCreateResponse) => void) | undefined;
    const createFile = vi.fn(
      (request: FileCreateInput): Promise<FileCreateResponse> => {
        if (request.name === "failure.txt") {
          return Promise.reject(new Error("Connection lost"));
        }
        return new Promise((resolve) => {
          finishSlowUpload = resolve;
        });
      },
    );
    const onFileProcessed = vi.fn();

    const upload = uploadFilesToDestination({
      files: [failedFile, slowFile],
      destinationPath: filePath("/workspace/data"),
      createFile,
      onFileProcessed,
    });

    await vi.waitFor(() => {
      expect(createFile).toHaveBeenCalledTimes(2);
      expect(onFileProcessed).toHaveBeenCalledTimes(1);
    });
    let hasSettled = false;
    void upload.finally(() => {
      hasSettled = true;
    });
    await Promise.resolve();
    expect(hasSettled).toBe(false);

    finishSlowUpload?.({ success: true });
    await expect(upload).resolves.toEqual({
      successful: [{ file: slowFile, response: { success: true } }],
      failed: [
        {
          file: failedFile,
          response: { success: false, message: "Connection lost" },
        },
      ],
    });
    expect(onFileProcessed).toHaveBeenCalledTimes(2);
  });
});

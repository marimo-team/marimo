/* Copyright 2024 Marimo. All rights reserved. */

import { type DropzoneOptions, useDropzone } from "react-dropzone";
import { toast } from "@/components/ui/use-toast";
import { sendCreateFileOrFolder } from "@/core/network/requests";
import { serializeBlob } from "@/utils/blob";
import { Logger } from "@/utils/Logger";
import { type FilePath, PathBuilder } from "@/utils/paths";
import { refreshRoot } from "./state";

const MAX_SIZE = 1024 * 1024 * 100; // 100MB

export function useFileExplorerUpload(options: DropzoneOptions = {}) {
  return useDropzone({
    multiple: true,
    maxSize: MAX_SIZE,
    onError: (error) => {
      Logger.error(error);
      toast({
        title: "File upload failed",
        description: error.message,
        variant: "danger",
      });
    },
    onDropRejected: (rejectedFiles) => {
      toast({
        title: "File upload failed",
        description: (
          <div className="flex flex-col gap-1">
            {rejectedFiles.map((file) => (
              <div key={file.file.name}>
                {file.file.name} ({file.errors.map((e) => e.message).join(", ")}
                )
              </div>
            ))}
          </div>
        ),
        variant: "danger",
      });
    },
    onDrop: async (acceptedFiles) => {
      for (const file of acceptedFiles) {
        // We strip the leading slash since File.path can return
        // `/path/to/file`.
        const filePath = stripLeadingSlash(getPath(file));
        let directoryPath = "" as FilePath;
        if (filePath) {
          directoryPath =
            PathBuilder.guessDeliminator(filePath).dirname(filePath);
        }

        // File contents are sent base64-encoded to support arbitrary
        // bytes data
        //
        // get the raw base64-encoded data from a string starting with
        // data:*/*;base64,
        const base64 = (await serializeBlob(file)).split(",")[1];
        await sendCreateFileOrFolder({
          path: directoryPath,
          type: "file",
          name: file.name,
          contents: base64,
        });
      }
      await refreshRoot();
    },
    ...options,
  });
}

/**
 * Get the path of a file.
 *
 * Types only have `webkitRelativePath`, but File objects in the browser
 * can have `path` and `relativePath`.
 */
function getPath(file: File): FilePath | undefined {
  if (file.webkitRelativePath) {
    return file.webkitRelativePath as FilePath;
  }
  if ("path" in file && typeof file.path === "string") {
    return file.path as FilePath;
  }
  if ("relativePath" in file && typeof file.relativePath === "string") {
    return file.relativePath as FilePath;
  }
  return undefined;
}

/**
 * Strip leading slashes from a path.
 *
 * TODO: this may not support windows paths.
 */
function stripLeadingSlash(path: FilePath | undefined): FilePath | undefined {
  if (!path) {
    return undefined;
  }
  return path.replace(/^\/+/, "") as FilePath;
}

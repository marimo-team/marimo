/* Copyright 2024 Marimo. All rights reserved. */

import { type DropzoneOptions, useDropzone } from "react-dropzone";
import { toast } from "@/components/ui/use-toast";
import { sendCreateFileOrFolder } from "@/core/network/requests";
import { serializeBlob } from "@/utils/blob";
import { Logger } from "@/utils/Logger";
import type { FilePath } from "@/utils/paths";
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
        // File contents are sent base64-encoded to support arbitrary
        // bytes data
        //
        // get the raw base64-encoded data from a string starting with
        // data:*/*;base64,
        const base64 = (await serializeBlob(file)).split(",")[1];
        await sendCreateFileOrFolder({
          path: "" as FilePath, // add to root
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

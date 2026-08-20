/* Copyright 2026 Marimo. All rights reserved. */

import {
  type DropEvent,
  type DropzoneOptions,
  useDropzone,
} from "react-dropzone";
import { toast } from "@/components/ui/use-toast";
import { useRequestClient } from "@/core/network/requests";
import type { FileCreateInput, FileCreateResponse } from "@/core/network/types";
import { withLoadingToast } from "@/utils/download";
import { Logger } from "@/utils/Logger";
import { type FilePath, PathBuilder } from "@/utils/paths";
import { mapWithConcurrency } from "@/utils/semaphore";

const MAX_SIZE = 1024 * 1024 * 100; // 100MB
const UPLOAD_CONCURRENCY = 5;

export const FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE =
  "data-file-explorer-directory-path";

type DestinationPath = FilePath | ((event: DropEvent) => FilePath);

interface FileExplorerUploadOptions extends Omit<
  DropzoneOptions,
  "onDrop" | "onDropRejected" | "onError"
> {
  destinationPath: DestinationPath;
  getDestinationLabel?: (path: FilePath) => string;
  onUploadStart?: (destinationPath: FilePath, files: File[]) => void;
  refreshDestination: (destinationPath: FilePath) => Promise<void>;
}

interface UploadFileResult {
  file: File;
  response: FileCreateResponse;
}

export interface UploadFilesResult {
  successful: UploadFileResult[];
  failed: UploadFileResult[];
}

export function useFileExplorerUpload(options: FileExplorerUploadOptions) {
  const {
    destinationPath,
    getDestinationLabel = (path) => path,
    onUploadStart,
    refreshDestination,
    ...dropzoneOptions
  } = options;
  const { sendCreateFileOrFolder } = useRequestClient();

  return useDropzone({
    multiple: true,
    maxSize: MAX_SIZE,
    ...dropzoneOptions,
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
    onDrop: async (acceptedFiles, _rejectedFiles, event) => {
      if (acceptedFiles.length === 0) {
        return;
      }

      const resolvedDestinationPath =
        typeof destinationPath === "function"
          ? destinationPath(event)
          : destinationPath;
      const destinationLabel = getDestinationLabel(resolvedDestinationPath);
      const isSingle = acceptedFiles.length === 1;
      const loadingTitle = isSingle
        ? `Uploading file to ${destinationLabel}...`
        : `Uploading files to ${destinationLabel}...`;

      onUploadStart?.(resolvedDestinationPath, acceptedFiles);

      let result: UploadFilesResult;
      try {
        result = await withLoadingToast(loadingTitle, async (progress) => {
          progress.addTotal(acceptedFiles.length);
          return uploadFilesToDestination({
            files: acceptedFiles,
            destinationPath: resolvedDestinationPath,
            createFile: sendCreateFileOrFolder,
            onFileProcessed: () => progress.increment(1),
          });
        });
      } catch {
        await refreshDestination(resolvedDestinationPath);
        return;
      }

      await refreshDestination(resolvedDestinationPath);
      showUploadResultToast(result, destinationLabel);
    },
  });
}

export async function uploadFilesToDestination({
  files,
  destinationPath,
  createFile,
  onFileProcessed,
}: {
  files: File[];
  destinationPath: FilePath;
  createFile: (request: FileCreateInput) => Promise<FileCreateResponse>;
  onFileProcessed?: () => void;
}): Promise<UploadFilesResult> {
  const results = await mapWithConcurrency(
    files,
    UPLOAD_CONCURRENCY,
    async (file): Promise<UploadFileResult> => {
      const filePath = stripLeadingSlash(getPath(file));
      const directoryPath = resolveUploadDirectoryPath({
        destinationPath,
        filePath,
      });
      const response = await createFile({
        path: directoryPath,
        type: "file",
        name: file.name,
        file,
      });
      onFileProcessed?.();
      return { file, response };
    },
  );

  return {
    successful: results.filter(({ response }) => response.success),
    failed: results.filter(({ response }) => !response.success),
  };
}

export function resolveUploadDirectoryPath({
  destinationPath,
  filePath,
}: {
  destinationPath: FilePath;
  filePath: FilePath | undefined;
}): FilePath {
  if (!filePath) {
    return destinationPath;
  }

  const filePathBuilder = PathBuilder.guessDeliminator(filePath);
  const relativeDirectoryPath = filePathBuilder.dirname(filePath);
  if (!relativeDirectoryPath || relativeDirectoryPath === ".") {
    return destinationPath;
  }

  const destinationPathBuilder = PathBuilder.guessDeliminator(destinationPath);
  const normalizedRelativePath = relativeDirectoryPath
    .split(filePathBuilder.deliminator)
    .join(destinationPathBuilder.deliminator);
  return destinationPathBuilder.join(destinationPath, normalizedRelativePath);
}

export function getUploadDestinationFromTarget(
  target: EventTarget | null,
  rootPath: FilePath,
): FilePath {
  if (!(target instanceof Element)) {
    return rootPath;
  }

  const directory = target.closest(
    `[${FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE}]`,
  );
  const path = directory?.getAttribute(FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE);
  return path ? (path as FilePath) : rootPath;
}

function showUploadResultToast(
  result: UploadFilesResult,
  destinationLabel: string,
) {
  const total = result.successful.length + result.failed.length;
  if (result.failed.length > 0) {
    toast({
      title:
        result.successful.length === 0
          ? "File upload failed"
          : `${result.successful.length} of ${total} files uploaded`,
      description: (
        <div className="flex flex-col gap-1">
          <div>Destination: {destinationLabel}.</div>
          {result.failed.map(({ file, response }, index) => (
            <div key={`${file.name}-${index}`}>
              {file.name}:{" "}
              {response.message || "The server rejected the upload."}
            </div>
          ))}
        </div>
      ),
      variant: "danger",
    });
    return;
  }

  const renamedFiles = result.successful.filter(
    ({ file, response }) =>
      response.info?.name && response.info.name !== file.name,
  );
  toast({
    title: total === 1 ? "File uploaded" : `${total} files uploaded`,
    description:
      renamedFiles.length === 0 ? (
        `Uploaded to ${destinationLabel}.`
      ) : (
        <div className="flex flex-col gap-1">
          <div>Uploaded to {destinationLabel}.</div>
          {renamedFiles.map(({ file, response }, index) => (
            <div key={`${file.name}-${index}`}>
              {file.name} was saved as {response.info?.name}.
            </div>
          ))}
        </div>
      ),
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

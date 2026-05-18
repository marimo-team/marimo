/* Copyright 2026 Marimo. All rights reserved. */

import { SimpleTree } from "react-arborist";
import { toast } from "@/components/ui/use-toast";
import type {
  EditRequests,
  FileInfo,
  FileUpdateResponse,
} from "@/core/network/types";
import { prettyError } from "@/utils/errors";
import { Functions } from "@/utils/functions";
import { type FilePath, PathBuilder } from "@/utils/paths";
import { resolvePaths } from "@/utils/pathUtils";
import { mapWithConcurrency } from "@/utils/semaphore";

const FILE_OP_CONCURRENCY = 5;

/**
 * Normalized result of a file mutation: the server response when successful,
 * `null` when the server rejected the request and a toast was surfaced.
 */
export type FileOperationResult = FileUpdateResponse | null;

export function handleFileResponse(
  response: FileUpdateResponse,
): FileOperationResult {
  if (!response.success) {
    toast({
      title: "Failed",
      description: response.message,
    });
    return null;
  }
  return response;
}

export class RequestingTree {
  private delegate = new SimpleTree<FileInfo>([]);
  private callbacks: {
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  };

  constructor(callbacks: {
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  }) {
    this.callbacks = callbacks;
  }

  private rootPath: FilePath = "" as FilePath;
  private onChange: (data: FileInfo[]) => void = Functions.NOOP;
  private path = new PathBuilder("/");

  initialize = async (onChange: (data: FileInfo[]) => void): Promise<void> => {
    this.onChange = onChange;
    if (this.delegate.data.length === 0) {
      try {
        const data = await this.callbacks.listFiles({ path: this.rootPath });
        this.delegate = new SimpleTree(data.files);
        this.rootPath = data.root as FilePath;
        this.path = PathBuilder.guessDeliminator(data.root);
      } catch (error) {
        toast({
          title: "Failed",
          description: prettyError(error),
        });
      }
    }

    this.onChange(this.delegate.data);
  };

  async expand(id: string): Promise<boolean> {
    const node = this.delegate.find(id);
    if (!node) {
      return false;
    }
    if (!node.data.isDirectory) {
      return false;
    }

    // We may attempt to load empty directories multiple times
    // but that is fine
    if (node.children && node.children.length > 0) {
      // Already loaded
      return true;
    }

    const data = await this.callbacks.listFiles({ path: node.data.path });
    this.delegate.update({ id, changes: { children: data.files } });
    this.onChange(this.delegate.data);
    return true;
  }

  async copy(id: string, newName: string): Promise<void> {
    const node = this.delegate.find(id);
    if (!node) {
      toast({
        title: "Failed",
        description: `Node with id ${id} not found in the tree`,
      });
      return;
    }
    const { path, newPath } = resolvePaths({
      path: node.data.path,
      name: newName,
      root: this.rootPath,
    });
    const parentPath = this.path.dirname(path);
    const newFile = await this.callbacks
      .copyFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (!newFile?.info) {
      return;
    }
    this.delegate.create({
      parentId: node.parent?.id ?? null,
      index: 0,
      data: newFile.info,
    });
    this.onChange(this.delegate.data);
    // Refresh the parent folder
    await this.refreshAll([parentPath]);
  }

  async rename(id: string, name: string): Promise<void> {
    const node = this.delegate.find(id);
    if (!node) {
      toast({
        title: "Failed",
        description: `Node with id ${id} not found in the tree`,
      });
      return;
    }
    const { path, newPath } = resolvePaths({
      path: node.data.path,
      name,
      root: this.rootPath,
    });
    const result = await this.callbacks
      .renameFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (!result) {
      return;
    }

    this.delegate.update({ id, changes: { name, path: newPath } });
    this.onChange(this.delegate.data);
    // Rename all of its children
    await this.refreshAll([newPath]);
  }

  async move(fromIds: string[], parentId: string | null): Promise<void> {
    const parentPath = parentId
      ? (this.delegate.find(parentId)?.data.path ?? parentId)
      : this.rootPath;

    await mapWithConcurrency(fromIds, FILE_OP_CONCURRENCY, async (id) => {
      const node = this.delegate.find(id);
      if (!node) {
        return;
      }
      const originalPath = node.data.path;
      const newPath = this.path.join(
        parentPath,
        this.path.basename(originalPath as FilePath),
      );
      const result = await this.callbacks
        .renameFileOrFolder({ path: originalPath, newPath })
        .then(handleFileResponse);
      if (!result) {
        return;
      }

      this.delegate.move({ id, parentId, index: 0 });
      this.delegate.update({ id, changes: { path: newPath } });
    });

    this.onChange(this.delegate.data);

    // Refresh the parent folder
    await this.refreshAll([parentPath]);
  }

  async createFile({
    name,
    parentId,
    type = "file",
  }: {
    name: string;
    parentId: string | null;
    type?: "file" | "notebook";
  }): Promise<void> {
    const parentPath = parentId
      ? (this.delegate.find(parentId)?.data.path ?? parentId)
      : this.rootPath;
    const newFile = await this.callbacks
      .createFileOrFolder({ path: parentPath, type: type, name: name })
      .then(handleFileResponse);
    if (!newFile?.info) {
      return;
    }
    this.delegate.create({
      parentId,
      index: 0,
      data: newFile.info,
    });
    this.onChange(this.delegate.data);
    // Refresh the parent folder
    await this.refreshAll([parentPath]);
  }

  async createFolder(name: string, parentId: string | null): Promise<void> {
    const parentPath = parentId
      ? (this.delegate.find(parentId)?.data.path ?? parentId)
      : this.rootPath;
    const newFolder = await this.callbacks
      .createFileOrFolder({ path: parentPath, type: "directory", name: name })
      .then(handleFileResponse);
    if (!newFolder?.info) {
      return;
    }
    this.delegate.create({
      parentId,
      index: 0,
      data: newFolder.info,
    });
    this.onChange(this.delegate.data);
    // Refresh the parent folder
    await this.refreshAll([parentPath]);
  }

  async delete(id: string): Promise<void> {
    const node = this.delegate.find(id);
    if (!node) {
      toast({
        title: "Failed",
        description: `Node with id ${id} not found in the tree`,
      });
      return;
    }

    const result = await this.callbacks
      .deleteFileOrFolder({ path: node.data.path })
      .then(handleFileResponse);
    if (!result) {
      return;
    }
    this.delegate.drop({ id });
    this.onChange(this.delegate.data);
  }

  refreshAll = async (ids: string[]): Promise<void> => {
    // For each open folder, refresh
    const openFolders = [
      this.rootPath,
      ...ids.map((id) => this.delegate.find(id)?.data.path),
    ].filter(Boolean);
    // Request open folders with bounded concurrency; swallow per-folder errors.
    const data = await mapWithConcurrency(
      openFolders,
      FILE_OP_CONCURRENCY,
      (path) =>
        this.callbacks.listFiles({ path: path }).catch(() => ({ files: [] })),
    );

    for (const [idx, openFolder] of openFolders.entries()) {
      const datum = data[idx];
      if (openFolder === this.rootPath) {
        this.delegate = new SimpleTree(datum.files);
      } else {
        this.delegate.update({
          id: openFolder,
          changes: { children: datum.files },
        });
      }
    }

    this.onChange(this.delegate.data);
  };

  public relativeFromRoot = (path: FilePath): FilePath => {
    // Add a trailing delimiter to the root path if it doesn't have one
    const root = this.rootPath.endsWith(this.path.deliminator)
      ? this.rootPath
      : `${this.rootPath}${this.path.deliminator}`;

    if (path.startsWith(root)) {
      return path.slice(root.length) as FilePath;
    }
    return path;
  };
}

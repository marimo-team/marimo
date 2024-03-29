/* Copyright 2024 Marimo. All rights reserved. */
import { toast } from "@/components/ui/use-toast";
import type {
  sendListFiles,
  sendCreateFileOrFolder,
  sendDeleteFileOrFolder,
  sendRenameFileOrFolder,
} from "@/core/network/requests";
import { FileInfo, FileOperationResponse } from "@/core/network/types";
import { prettyError } from "@/utils/errors";
import { Functions } from "@/utils/functions";
import { FilePath, PathBuilder } from "@/utils/paths";
import { SimpleTree } from "react-arborist";

export class RequestingTree {
  private delegate = new SimpleTree<FileInfo>([]);

  constructor(
    private callbacks: {
      listFiles: typeof sendListFiles;
      createFileOrFolder: typeof sendCreateFileOrFolder;
      deleteFileOrFolder: typeof sendDeleteFileOrFolder;
      renameFileOrFolder: typeof sendRenameFileOrFolder;
    },
  ) {}

  private rootPath: FilePath = "" as FilePath;
  private onChange: (data: FileInfo[]) => void = Functions.NOOP;
  private path = new PathBuilder("/");

  initialize = async (onChange: (data: FileInfo[]) => void): Promise<void> => {
    this.onChange = onChange;
    if (this.delegate.data.length === 0) {
      try {
        const data = await this.callbacks.listFiles({ path: this.rootPath });
        this.delegate = new SimpleTree(data.files);
        this.rootPath = data.root;
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

  async rename(id: string, name: string): Promise<void> {
    const node = this.delegate.find(id);
    if (!node) {
      return;
    }
    const currentPath = node.data.path;
    const newPath = this.path.join(this.path.dirname(currentPath), name);
    await this.callbacks
      .renameFileOrFolder({
        path: currentPath,
        newPath: newPath,
      })
      .then(this.handleResponse);
    this.delegate.update({ id, changes: { name, path: newPath } });
    this.onChange(this.delegate.data);
  }

  async move(fromIds: string[], parentId: string | null): Promise<void> {
    const parentPath = parentId
      ? this.delegate.find(parentId)?.data.path ?? parentId
      : this.rootPath;

    await Promise.all(
      fromIds.map((id) => {
        this.delegate.move({ id, parentId, index: 0 });
        const node = this.delegate.find(id);
        if (!node) {
          return Promise.resolve();
        }
        const newPath = this.path.join(
          parentPath,
          this.path.basename(node.data.path),
        );
        this.delegate.update({ id, changes: { path: newPath } });
        return this.callbacks
          .renameFileOrFolder({
            path: node.data.path,
            newPath: newPath,
          })
          .then(this.handleResponse);
      }),
    );

    this.onChange(this.delegate.data);

    // Refresh the parent folder
    await this.refreshAll([parentPath]);
  }

  async delete(id: string): Promise<void> {
    const node = this.delegate.find(id);
    if (!node) {
      return;
    }

    await this.callbacks
      .deleteFileOrFolder({ path: node.data.path })
      .then(this.handleResponse);
    this.delegate.drop({ id });
    this.onChange(this.delegate.data);
  }

  refreshAll = async (ids: string[]): Promise<void> => {
    // For each open folder, refresh
    const openFolders = [
      this.rootPath,
      ...ids.map((id) => this.delegate.find(id)?.data.path),
    ].filter(Boolean);
    // Request all folders in parallel, and catch any errors
    const data = await Promise.all(
      openFolders.map((path) =>
        this.callbacks.listFiles({ path: path }).catch(() => ({ files: [] })),
      ),
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

  private handleResponse = (response: FileOperationResponse): void => {
    if (!response.success) {
      toast({
        title: "Failed",
        description: response.message,
      });
      return;
    }
  };
}

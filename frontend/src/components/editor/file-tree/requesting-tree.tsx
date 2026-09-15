/* Copyright 2026 Marimo. All rights reserved. */

import { SimpleTree } from "react-arborist";
import { toast } from "@/components/ui/use-toast";
import type {
  EditRequests,
  FileInfo,
  FileRoot,
  FileUpdateResponse,
} from "@/core/network/types";
import { prettyError } from "@/utils/errors";
import { Functions } from "@/utils/functions";
import { type FilePath, PathBuilder } from "@/utils/paths";
import { mapWithConcurrency } from "@/utils/semaphore";

const FILE_OP_CONCURRENCY = 5;
const WINDOWS_DRIVE_PATH = /^[A-Za-z]:[/\\]/;
const WINDOWS_UNC_PATH = /^\\\\/;

export type FileTreeNode = Omit<FileInfo, "children"> & {
  children: FileTreeNode[];
  isRoot: boolean;
  rootPath: string;
  isPrimaryRoot: boolean;
  loadState?: "unloaded" | "loading" | "loaded" | "error";
};

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
  private delegate = new SimpleTree<FileTreeNode>([]);
  private readonly callbacks: {
    getRoots: EditRequests["getFileRoots"];
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  };

  constructor(callbacks: {
    getRoots: EditRequests["getFileRoots"];
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  }) {
    this.callbacks = callbacks;
  }

  private roots: FileRoot[] = [];
  private pendingExpansions = new Map<string, Promise<boolean>>();
  private onChange: (data: FileTreeNode[]) => void = Functions.NOOP;
  private path = new PathBuilder("/");

  initialize = async (
    onChange: (data: FileTreeNode[]) => void,
  ): Promise<void> => {
    this.onChange = onChange;
    if (this.delegate.data.length === 0) {
      try {
        const { roots } = await this.callbacks.getRoots();
        const primaryRoot = roots.find((root) => root.isPrimary);
        if (!primaryRoot) {
          throw new Error("File browser response is missing a primary root");
        }
        this.roots = roots;
        this.path = PathBuilder.guessDeliminator(primaryRoot.path);
        this.delegate = new SimpleTree(roots.map(toRootNode));
        if (roots.length === 1) {
          const data = await this.callbacks.listFiles({
            path: primaryRoot.path,
          });
          this.updateDirectory(this.getPrimaryRootId(), data.files);
        }
      } catch (error) {
        toast({
          title: "Failed",
          description: prettyError(error),
        });
      }
    }

    this.emitChange();
  };

  expand(id: string): Promise<boolean> {
    return this.requestDirectory(id);
  }

  private requestDirectory(id: string, force = false): Promise<boolean> {
    const pending = this.pendingExpansions.get(id);
    if (pending) {
      return pending;
    }
    const node = this.delegate.find(id);
    if (!node?.data.isDirectory) {
      return Promise.resolve(false);
    }

    if (!force && node.data.loadState === "loaded") {
      return Promise.resolve(true);
    }

    const request = this.loadDirectory(id, node.data).finally(() => {
      this.pendingExpansions.delete(id);
    });
    this.pendingExpansions.set(id, request);
    return request;
  }

  private async loadDirectory(
    id: string,
    node: FileTreeNode,
  ): Promise<boolean> {
    this.delegate.update({ id, changes: { loadState: "loading" } });
    this.emitChange();
    try {
      const data = await this.callbacks.listFiles({ path: node.path });
      this.updateDirectory(id, data.files);
      return true;
    } catch (error) {
      this.delegate.update({ id, changes: { loadState: "error" } });
      toast({
        title: `Could not load ${node.name}`,
        description: prettyError(error),
      });
      return false;
    } finally {
      this.emitChange();
    }
  }

  getRoots(): readonly FileRoot[] {
    return this.roots;
  }

  async reveal(node: FileTreeNode): Promise<boolean> {
    const relative = relativePath(node.path as FilePath, node.rootPath);
    if (relative === null) {
      return false;
    }
    let path = node.rootPath as FilePath;
    const parts = relative.split(pathDelimiter(node.rootPath)).filter(Boolean);
    if (!node.isDirectory) {
      parts.pop();
    }
    for (const part of [null, ...parts]) {
      if (part !== null) {
        const parentId = fileTreeNodeId(node.rootPath, path);
        path = joinPath(path, part);
        // Search sees the live filesystem; a cached parent may not contain
        // a directory that was created since its last listing.
        if (!this.delegate.find(fileTreeNodeId(node.rootPath, path))) {
          if (!(await this.requestDirectory(parentId, true))) {
            return false;
          }
        }
      }
      const id = fileTreeNodeId(node.rootPath, path);
      if (!this.delegate.find(id)) {
        toast({
          title: "Could not reveal folder",
          description: `The folder may have moved or been deleted: ${path}`,
        });
        return false;
      }
      if (!(await this.expand(id))) {
        return false;
      }
    }
    return true;
  }

  async copy(id: string, newName: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const path = node.data.path as FilePath;
    const parentPath = this.getParentPath(node.data);
    const newPath = joinPath(parentPath, newName);
    const result = await this.callbacks
      .copyFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  async rename(id: string, name: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const path = node.data.path as FilePath;
    const parentPath = this.getParentPath(node.data);
    const newPath = joinPath(parentPath, name);
    const result = await this.callbacks
      .renameFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  async move(fromIds: string[], parentId: string | null): Promise<void> {
    const targetParentId = parentId ?? this.getPrimaryRootId();
    const parent = this.delegate.find(targetParentId);
    if (!parent?.data.isDirectory) {
      return;
    }

    const refreshPaths = new Set<string>();
    await mapWithConcurrency(fromIds, FILE_OP_CONCURRENCY, async (id) => {
      const node = this.getMutableNode(id, false);
      if (!node) {
        return;
      }
      const originalPath = node.data.path;
      const sourceParentPath = this.getParentPath(node.data);
      const newPath = joinPath(
        parent.data.path,
        this.path.basename(originalPath as FilePath),
      );
      const result = await this.callbacks
        .renameFileOrFolder({ path: originalPath, newPath })
        .then(handleFileResponse);
      if (result) {
        refreshPaths.add(parent.data.path);
        refreshPaths.add(sourceParentPath);
      }
    });

    await this.refreshPaths([...refreshPaths]);
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
    const parent = this.getParentNode(parentId);
    if (!parent) {
      return;
    }
    const result = await this.callbacks
      .createFileOrFolder({
        path: parent.data.path,
        type,
        name,
      })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parent.data.path as FilePath);
    }
  }

  async createFolder(name: string, parentId: string | null): Promise<void> {
    const parent = this.getParentNode(parentId);
    if (!parent) {
      return;
    }
    const result = await this.callbacks
      .createFileOrFolder({
        path: parent.data.path,
        type: "directory",
        name,
      })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parent.data.path as FilePath);
    }
  }

  async delete(id: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const parentPath = this.getParentPath(node.data);
    const result = await this.callbacks
      .deleteFileOrFolder({ path: node.data.path })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  refreshAll = async (ids: string[]): Promise<void> => {
    const paths = [
      ...this.roots.map((root) => root.path),
      ...ids
        .map((id) => this.delegate.find(id)?.data.path)
        .filter((path): path is string => Boolean(path)),
    ];
    await this.refreshPaths(
      paths,
      new Set([
        ...this.roots.map((root) => fileTreeNodeId(root.path, root.path)),
        ...ids,
      ]),
    );
  };

  refreshPath = async (path: FilePath): Promise<void> => {
    await this.refreshPaths([path]);
  };

  public getPrimaryRelativePath = (path: FilePath): FilePath | null => {
    const primaryRoot = this.getPrimaryRoot();
    if (!primaryRoot) {
      return null;
    }
    return relativePath(path, primaryRoot.path);
  };

  public getPrimaryRootPath = (): FilePath => {
    return (this.getPrimaryRoot()?.path ?? "") as FilePath;
  };

  public getPrimaryRootId = (): string => {
    const path = this.getPrimaryRoot()?.path ?? "";
    return fileTreeNodeId(path, path);
  };

  public isPrimaryNode = (node: FileTreeNode): boolean => {
    return node.isPrimaryRoot;
  };

  public getDisplayPath = (path: FilePath): string => {
    const root = this.getRootForPath(path);
    if (!root) {
      return path;
    }
    const relative = relativePath(path, root.path);
    if (!relative) {
      return root.name;
    }
    return root.isPrimary ? relative : `${root.name}/${relative}`;
  };

  public isRootPath = (path: FilePath): boolean => {
    return this.roots.some((root) => pathsEqual(path, root.path));
  };

  private getPrimaryRoot(): FileRoot | undefined {
    return this.roots.find((root) => root.isPrimary);
  }

  private getRootForNode(node: FileTreeNode): FileRoot {
    return (
      this.roots.find((root) => pathsEqual(root.path, node.rootPath)) ??
      this.getPrimaryRoot() ?? {
        path: node.rootPath,
        name: node.rootPath,
        isPrimary: node.isPrimaryRoot,
      }
    );
  }

  private getRootForPath(path: FilePath): FileRoot | undefined {
    return this.roots
      .filter((root) => relativePath(path, root.path) !== null)
      .toSorted((left, right) => right.path.length - left.path.length)[0];
  }

  private getParentNode(parentId: string | null) {
    const resolvedId = parentId ?? this.getPrimaryRootId();
    const node = this.delegate.find(resolvedId);
    return node?.data.isDirectory ? node : null;
  }

  private getParentPath(node: FileTreeNode): FilePath {
    const parent = this.delegate.find(node.id)?.parent;
    return (parent?.data.path ?? node.rootPath) as FilePath;
  }

  private getMutableNode(id: string, showError = true) {
    const node = this.delegate.find(id);
    if (!node || node.data.isRoot) {
      if (showError) {
        toast({
          title: "Failed",
          description: node
            ? "File browser roots cannot be modified"
            : `Node with id ${id} not found in the tree`,
        });
      }
      return null;
    }
    return node;
  }

  private refreshPaths = async (
    paths: string[],
    retainedIds?: ReadonlySet<string>,
  ): Promise<void> => {
    const uniquePaths = [...new Set(paths)].toSorted(
      (left, right) => left.length - right.length,
    );
    if (uniquePaths.length === 0) {
      return;
    }
    const results = await mapWithConcurrency(
      uniquePaths,
      FILE_OP_CONCURRENCY,
      (path) => this.callbacks.listFiles({ path }).catch(() => null),
    );

    for (const [index, path] of uniquePaths.entries()) {
      const result = results[index];
      if (!result) {
        continue;
      }
      // Fetch overlapping paths once, but retain loaded folders independently
      // for each root-qualified occurrence.
      for (const root of this.roots) {
        const id = fileTreeNodeId(root.path, path);
        if (!retainedIds || retainedIds.has(id)) {
          this.updateDirectory(id, result.files, retainedIds);
        }
      }
    }
    this.emitChange();
  };

  private updateDirectory(
    id: string,
    files: FileInfo[],
    retainedIds?: ReadonlySet<string>,
  ): void {
    const node = this.delegate.find(id)?.data;
    if (!node?.isDirectory) {
      return;
    }
    const children = mergeDirectoryChildren(
      annotateFiles(files, this.getRootForNode(node)),
      node.children,
    );
    this.delegate.update({
      id,
      changes: {
        children: retainedIds
          ? invalidateClosedDirectories(children, retainedIds)
          : children,
        loadState: "loaded",
      },
    });
  }

  private emitChange(): void {
    const data = this.delegate.data;
    // SimpleTree mutates child arrays in place. Publish a new array so React
    // observes completed directory loads even when the root is flattened.
    this.onChange(
      this.roots.length === 1 ? [...(data[0]?.children ?? [])] : data,
    );
  }
}

function mergeDirectoryChildren(
  files: FileTreeNode[],
  previous: FileTreeNode[],
): FileTreeNode[] {
  const byId = new Map(previous.map((node) => [node.id, node]));
  return files.map((file) => {
    const old = byId.get(file.id);
    if (!file.isDirectory || !old?.isDirectory) {
      return file;
    }
    return { ...file, children: old.children, loadState: old.loadState };
  });
}

function invalidateClosedDirectories(
  files: FileTreeNode[],
  openIds: ReadonlySet<string>,
): FileTreeNode[] {
  return files.map((file) => {
    if (!file.isDirectory) {
      return file;
    }
    if (!openIds.has(file.id)) {
      return { ...file, children: [], loadState: "unloaded" };
    }
    return {
      ...file,
      children: invalidateClosedDirectories(file.children, openIds),
    };
  });
}

function toRootNode(root: FileRoot): FileTreeNode {
  return {
    id: fileTreeNodeId(root.path, root.path),
    path: root.path,
    name: root.name,
    isDirectory: true,
    isMarimoFile: false,
    children: [],
    isRoot: true,
    rootPath: root.path,
    isPrimaryRoot: root.isPrimary,
    loadState: "unloaded",
  };
}

function annotateFiles(files: FileInfo[], root: FileRoot): FileTreeNode[] {
  return files.map((file) => ({
    ...file,
    id: fileTreeNodeId(root.path, file.path),
    children: annotateFiles(file.children ?? [], root),
    loadState: file.children?.length ? "loaded" : "unloaded",
    isRoot: false,
    rootPath: root.path,
    isPrimaryRoot: root.isPrimary,
  }));
}

/** A stable, globally unique tree ID for a path as viewed from one root. */
export function fileTreeNodeId(rootPath: string, path: string): string {
  return `${encodeURIComponent(rootPath)}:${encodeURIComponent(path)}`;
}

function relativePath(path: string, root: string): FilePath | null {
  const windowsPath = isWindowsPath(root);
  const normalizeCase = (value: string) =>
    windowsPath ? value.toLowerCase() : value;
  const comparedPath = normalizeCase(path);
  const comparedRoot = normalizeCase(root);
  if (comparedPath === comparedRoot) {
    return "" as FilePath;
  }

  const delimiter = pathDelimiter(root);
  const rootWithDelimiter = root.endsWith(delimiter)
    ? root
    : `${root}${delimiter}`;
  const comparedPrefix = normalizeCase(rootWithDelimiter);
  if (!comparedPath.startsWith(comparedPrefix)) {
    return null;
  }
  return path.slice(rootWithDelimiter.length) as FilePath;
}

function pathsEqual(left: string, right: string): boolean {
  return relativePath(left, right) === ("" as FilePath);
}

function joinPath(parent: string, name: string): FilePath {
  const delimiter = pathDelimiter(parent);
  return `${parent}${parent.endsWith(delimiter) ? "" : delimiter}${name}` as FilePath;
}

function isWindowsPath(path: string): boolean {
  return WINDOWS_DRIVE_PATH.test(path) || WINDOWS_UNC_PATH.test(path);
}

function pathDelimiter(path: string): "/" | "\\" {
  if (WINDOWS_UNC_PATH.test(path) || /^[A-Za-z]:\\/.test(path)) {
    return "\\";
  }
  return "/";
}

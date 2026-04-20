/* Copyright 2026 Marimo. All rights reserved. */

import { type FilePath, Paths, PathBuilder } from "./paths";

/**
 * Get the protocol and parent directories of a path.
 */
export function getProtocolAndParentDirectories({
  path,
  delimiter,
  initialPath,
  restrictNavigation,
}: {
  path: string;
  delimiter: string;
  initialPath: string;
  restrictNavigation: boolean;
}) {
  // Determine protocol (http://, gs://, C:\, s3://, or /)
  const protocolMatch = path.match(/^[\dA-Za-z]+:\/\//);
  const isWindowsPath = /^[A-Za-z]:\\/.test(path);
  const protocol = protocolMatch
    ? protocolMatch[0]
    : isWindowsPath
      ? path.slice(0, 3)
      : "/";

  // Remove protocol from path
  const pathWithoutProtocol = isWindowsPath
    ? path.slice(protocol.length)
    : protocolMatch
      ? path.slice(protocol.length)
      : path;

  // Split path into segments
  const segments = pathWithoutProtocol.split(delimiter).filter(Boolean);

  // Build parent directories from segments
  let parentDirectories: string[] = [];

  if (isWindowsPath) {
    // Handle Windows paths differently
    for (let i = segments.length; i >= 0; i--) {
      const dirPath = protocol + segments.slice(0, i).join(delimiter);
      parentDirectories.push(dirPath);
    }
  } else {
    // Handle non-Windows paths
    let currentPath = protocol;
    for (let i = 0; i <= segments.length; i++) {
      const dirPath = currentPath + segments.slice(0, i).join(delimiter);
      parentDirectories.push(dirPath);

      // Add delimiter if not already present
      if (i < segments.length && !currentPath.endsWith(delimiter)) {
        currentPath += delimiter;
      }
    }
    // Reverse to get parent directories in descending order
    parentDirectories.reverse();
  }

  // Filter to paths within initial path if navigation is restricted
  if (restrictNavigation) {
    parentDirectories = parentDirectories.filter((dir) =>
      dir.startsWith(initialPath),
    );
  }

  return { protocol, parentDirectories };
}

export function fileSplit(path: string): [name: string, extension: string] {
  const lastDotIndex = path.lastIndexOf(".");
  const name = lastDotIndex > 0 ? path.slice(0, lastDotIndex) : path;
  const extension = lastDotIndex > 0 ? path.slice(lastDotIndex) : "";
  return [name, extension];
}

/**
 * Build the "_copy" filename used for duplicate operations.
 * e.g. `foo.py` → `foo_copy.py`, `README` → `README_copy`.
 */
export function makeDuplicateName(name: string): string {
  const [base, extension] = fileSplit(name);
  return `${base}_copy${extension}`;
}

/**
 * Return `path` as an absolute path, joining against `root` when it's
 * workspace-relative. `root`'s delimiter determines the join style so
 * Windows and POSIX paths both behave correctly.
 */
export function toAbsolutePath(path: string, root: string): FilePath {
  if (Paths.isAbsolute(path)) {
    return path as FilePath;
  }
  return PathBuilder.guessDeliminator(root).join(root, path as FilePath);
}

/**
 * Resolve absolute current/new paths for a rename- or copy-style operation.
 * Given a node's current `path` (absolute or workspace-relative) and a
 * desired new `name` (basename only), returns the absolute source and the
 * absolute destination, keeping the file in the same parent directory.
 */
export function resolvePaths({
  path,
  name,
  root,
}: {
  path: string;
  name: string;
  root: string;
}): { path: FilePath; newPath: FilePath } {
  const absPath = toAbsolutePath(path, root);
  // When `root` is empty (callers with already-absolute paths), fall back to
  // the resolved absolute path so we don't default to the Windows delimiter.
  const pathBuilder = PathBuilder.guessDeliminator(root || absPath);
  const newPath = pathBuilder.join(pathBuilder.dirname(absPath), name);
  return { path: absPath, newPath };
}

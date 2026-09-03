/* Copyright 2026 Marimo. All rights reserved. */

import type { TypedString } from "./typed";

export type FilePath = TypedString<"FilePath">;

// Windows drive-letter prefix like `C:\`, `d:/`, `Z:\`.
const WINDOWS_DRIVE_PREFIX = /^[A-Za-z]:[/\\]/;
const WINDOWS_UNC_PREFIX = /^(?:\\\\|\/\/)[^/\\]+[/\\][^/\\]+/;
// URI scheme prefix like `s3://`, `gs://`, `http://`, `file://`.
const URI_SCHEME_PREFIX = /^[A-Za-z][\dA-Za-z+.-]*:\/\//;

export const Paths = {
  isAbsolute: (path: string): boolean => {
    return (
      path.startsWith("/") ||
      path.startsWith("\\") ||
      WINDOWS_DRIVE_PREFIX.test(path) ||
      URI_SCHEME_PREFIX.test(path)
    );
  },
  dirname: (path: string) => {
    return PathBuilder.guessDeliminator(path).dirname(path as FilePath);
  },
  basename: (path: string) => {
    return PathBuilder.guessDeliminator(path).basename(path as FilePath);
  },
  rest: (path: string, root: string) => {
    return PathBuilder.guessDeliminator(path).rest(
      path as FilePath,
      root as FilePath,
    );
  },
  extension: (filename: string): string => {
    const parts = filename.split(".");
    if (parts.length === 1) {
      return "";
    }
    return parts.at(-1) ?? "";
  },
};

/**
 * Return `path` relative to `root`, or `null` when it is outside the root.
 * Paths come from the server, so Windows semantics cannot depend on the
 * browser's operating system.
 */
export function relativeFilePath(
  path: FilePath,
  root: FilePath,
): FilePath | null {
  const isWindows =
    WINDOWS_DRIVE_PREFIX.test(root) || WINDOWS_UNC_PREFIX.test(root);
  const delimiter = isWindows ? "\\" : "/";
  const normalize = (value: FilePath): string =>
    isWindows ? value.replaceAll("/", "\\") : value;
  const forComparison = (value: string): string =>
    isWindows ? value.toLowerCase() : value;
  const normalizedPath = normalize(path);
  const normalizedRoot = trimTrailingSeparators(normalize(root), delimiter);
  const comparedPath = forComparison(normalizedPath);
  const comparedRoot = forComparison(normalizedRoot);
  if (comparedPath === comparedRoot) {
    return "" as FilePath;
  }

  const rootPrefix = normalizedRoot.endsWith(delimiter)
    ? normalizedRoot
    : `${normalizedRoot}${delimiter}`;
  if (!comparedPath.startsWith(forComparison(rootPrefix))) {
    return null;
  }
  return normalizedPath.slice(rootPrefix.length) as FilePath;
}

function trimTrailingSeparators(path: string, delimiter: "/" | "\\"): string {
  if (path === delimiter || /^[A-Za-z]:\\$/.test(path)) {
    return path;
  }
  while (path.endsWith(delimiter)) {
    path = path.slice(0, -1);
  }
  return path;
}

export class PathBuilder {
  public readonly deliminator: string;
  constructor(deliminator: "/" | "\\") {
    this.deliminator = deliminator;
  }

  static guessDeliminator(path: string): PathBuilder {
    return path.includes("/") ? new PathBuilder("/") : new PathBuilder("\\");
  }

  join(...paths: string[]): FilePath {
    let joined = "";
    for (const part of paths) {
      if (!part) {
        continue;
      }
      if (!joined) {
        joined = part;
        continue;
      }
      const joinedHasDelimiter = joined.endsWith(this.deliminator);
      const partHasDelimiter = part.startsWith(this.deliminator);
      if (joinedHasDelimiter && partHasDelimiter) {
        joined += part.slice(1);
      } else if (joinedHasDelimiter || partHasDelimiter) {
        joined += part;
      } else {
        joined += `${this.deliminator}${part}`;
      }
    }
    return joined as FilePath;
  }

  basename(path: FilePath): FilePath {
    const parts = path.split(this.deliminator);
    return (parts.pop() ?? "") as FilePath;
  }

  rest(path: FilePath, root: FilePath): FilePath {
    const pathParts = path.split(this.deliminator);
    const rootParts = root.split(this.deliminator);
    let i = 0;
    for (; i < pathParts.length && i < rootParts.length; ++i) {
      if (pathParts[i] !== rootParts[i]) {
        break;
      }
    }
    return pathParts.slice(i).join(this.deliminator) as FilePath;
  }

  dirname(path: FilePath): FilePath {
    const parts = path.split(this.deliminator);
    parts.pop();
    return parts.join(this.deliminator) as FilePath;
  }
}

/* Copyright 2024 Marimo. All rights reserved. */

import { filenameAtom } from "@/core/saving/filename";
import type { TypedString } from "./typed";
import { store } from "@/core/state/jotai";

export type FilePath = TypedString<"FilePath">;

export const Paths = {
  isAbsolute: (path: string): boolean => {
    return (
      path.startsWith("/") || path.startsWith("\\") || path.startsWith("C:\\")
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
  filenameWithDirectory: () => {
    const filename = store.get(filenameAtom);
    if (!filename) {
      return null;
    }
    const filenameWithDirectory = Paths.dirname(filename);
    return filenameWithDirectory;
  },
};

export class PathBuilder {
  constructor(public readonly deliminator: "/" | "\\") {}

  static guessDeliminator(path: string): PathBuilder {
    return path.includes("/") ? new PathBuilder("/") : new PathBuilder("\\");
  }

  join(...paths: string[]): FilePath {
    return paths.filter(Boolean).join(this.deliminator) as FilePath;
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

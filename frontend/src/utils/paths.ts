/* Copyright 2024 Marimo. All rights reserved. */

import { TypedString } from "./typed";

export type FilePath = TypedString<"FilePath">;

export const Paths = {
  dirname: (path: string) => {
    return PathBuilder.guessDeliminator(path).dirname(path as FilePath);
  },
  basename: (path: string) => {
    return PathBuilder.guessDeliminator(path).basename(path as FilePath);
  },
};

export class PathBuilder {
  constructor(private deliminator: "/" | "\\") {}

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

  dirname(path: FilePath): FilePath {
    const parts = path.split(this.deliminator);
    parts.pop();
    return parts.join(this.deliminator) as FilePath;
  }
}

/* Copyright 2024 Marimo. All rights reserved. */
export const Paths = {
  dirname: (path: string) => {
    const delimiter = path.includes("/") ? "/" : "\\";
    const parts = path.split(delimiter);
    parts.pop();
    return parts.join(delimiter);
  },
  basename: (path: string) => {
    const parts = path.split(/[/\\]/);
    return parts.pop() ?? "";
  },
};

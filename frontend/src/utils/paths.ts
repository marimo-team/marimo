/* Copyright 2024 Marimo. All rights reserved. */
export const Paths = {
  dirname: (path: string) => {
    const parts = path.split("/");
    parts.pop();
    return parts.join("/");
  },
  basename: (path: string) => {
    return path.split("/").pop() ?? "";
  },
};

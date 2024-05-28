/* Copyright 2024 Marimo. All rights reserved. */
export const Filenames = {
  toMarkdown: (filename: string): string => {
    return Filenames.replace(filename, "md");
  },
  toHTML: (filename: string): string => {
    return Filenames.replace(filename, "html");
  },
  toPNG: (filename: string): string => {
    return Filenames.replace(filename, "png");
  },
  toPY: (filename: string): string => {
    return Filenames.replace(filename, "py");
  },
  withoutExtension: (filename: string): string => {
    // Just remove the last extension
    const parts = filename.split(".");
    if (parts.length === 1) {
      return filename;
    }
    return parts.slice(0, -1).join(".");
  },
  replace: (filename: string, extension: string): string => {
    if (filename.endsWith(`.${extension}`)) {
      return filename;
    }
    return `${Filenames.withoutExtension(filename)}.${extension}`;
  },
};

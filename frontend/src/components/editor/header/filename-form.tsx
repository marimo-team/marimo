/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import { FilenameInput } from "@/components/editor/header/filename-input";
import { useUpdateFilename } from "@/core/saving/filename";
import { useSaveNotebook } from "@/core/saving/save-component";
import { Paths } from "@/utils/paths";

export const FilenameForm = ({
  filename,
}: {
  filename: string | null;
}): JSX.Element => {
  const updateFilename = useUpdateFilename();
  const { saveNotebook } = useSaveNotebook();

  const handleNameChange = (newFilename: string) => {
    const wasUnnamed = filename === null;
    updateFilename(newFilename).then((name) => {
      // When creating a new file (was unnamed), also save the content
      if (name !== null && wasUnnamed) {
        saveNotebook(name, true);
      }
    });
  };

  return (
    <FilenameInput
      placeholderText={
        filename ? Paths.basename(filename) : "untitled marimo notebook"
      }
      initialValue={filename}
      onNameChange={handleNameChange}
      flexibleWidth={true}
      resetOnBlur={true}
      data-testid="filename-input"
      className={filename === null ? "missing-filename" : "filename"}
    />
  );
};

/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react";
import { FilenameInput } from "@/components/editor/header/filename-input";
import { useUpdateFilename } from "@/core/saving/filename";
import { Paths } from "@/utils/paths";

export const FilenameForm = ({
  filename,
}: {
  filename: string | null;
}): JSX.Element => {
  const setFilename = useUpdateFilename();
  return (
    <FilenameInput
      placeholderText={
        filename ? Paths.basename(filename) : "untitled marimo notebook"
      }
      initialValue={filename}
      onNameChange={setFilename}
      flexibleWidth={true}
      resetOnBlur={true}
      data-testid="filename-input"
      className={filename === null ? "missing-filename" : "filename"}
    />
  );
};

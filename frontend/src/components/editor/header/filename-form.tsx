/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import {
  FilenameInput,
  FilenameInputDataId,
} from "@/components/editor/header/filename-input";
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
      data-testid={FilenameInputDataId}
      className={filename === null ? "missing-filename" : "filename"}
    />
  );
};

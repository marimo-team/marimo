/* Copyright 2024 Marimo. All rights reserved. */
import { FilenameInput } from "@/components/editor/header/filename-input";
import { Paths } from "@/utils/paths";

export const FilenameForm = ({
  filename,
  setFilename,
}: {
  filename: string | null;
  setFilename: (filename: string) => void;
}): JSX.Element => {
  return (
    <FilenameInput
      placeholderText={
        filename ? Paths.basename(filename) : "untitled marimo app"
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

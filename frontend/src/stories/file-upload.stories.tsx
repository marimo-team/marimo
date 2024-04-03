/* Copyright 2024 Marimo. All rights reserved. */
import { FileUpload } from "@/plugins/impl/FileUploadPlugin";

export default {
  title: "File Upload",
  component: FileUpload,
};

export const AcceptAny = {
  render: () => (
    <FileUpload
      filetypes={[]}
      multiple={true}
      kind="area"
      label={null}
      value={[]}
      setValue={() => null}
    />
  ),

  name: "Accept any",
};

export const AcceptLongText = {
  render: () => (
    <FileUpload
      filetypes={[]}
      multiple={true}
      kind="area"
      label={"Drop here, ".repeat(100)}
      value={[]}
      setValue={() => null}
    />
  ),

  name: "Accept long text",
};

export const AcceptTxtOnly = {
  render: () => (
    <FileUpload
      filetypes={[".txt"]}
      multiple={true}
      kind="area"
      label={null}
      value={[]}
      setValue={() => null}
    />
  ),

  name: "Accept .txt only",
};

export const AcceptTxtOnlyButton = {
  render: () => (
    <FileUpload
      filetypes={[".txt"]}
      multiple={true}
      kind="button"
      label={null}
      value={[]}
      setValue={() => null}
    />
  ),

  name: "Accept .txt only, button",
};

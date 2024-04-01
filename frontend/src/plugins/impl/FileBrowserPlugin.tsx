/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";
import { Table, TableCell, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

/**
 * Arguments for a file browser component.
 *
 * @param path - the path to display on component render
 * @param filetypes - filter directory lists by file types
 * @param multiple - whether to allow the user to select multiple files
 * @param label - label for the file browser
 * @param restrictNavigation - whether to prevent the user from accessing
 * directories outside the set path
 */
interface Data {
  path: string;
  files: string[];
  filetypes: string[];
  multiple: boolean;
  label: string | null;
  restrictNavigation: boolean;
}

type T = Array<[string]>;

export class FileBrowserPlugin implements IPlugin<T, Data> {
  tagName = "marimo-file-browser";

  validator = z.object({
    path: z.string(),
    files: z.array(z.string()),
    filetypes: z.array(z.string()),
    multiple: z.boolean(),
    label: z.string().nullable(),
    restrictNavigation: z.boolean(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <FileBrowser
        label={props.data.label}
        path={props.data.path}
        files={props.data.files}
        filetypes={props.data.filetypes}
        multiple={props.data.multiple}
        restrictNavigation={props.data.restrictNavigation}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

/**
 * @param value - array of selected (filename, path) tuples
 * @param setValue - sets selected files as component value
 */
interface FileBrowserProps extends Data {
  value: T;
  setValue: Setter<T>;
}

export const FileBrowser = (props: FileBrowserProps): JSX.Element => {
  const fileRows = props.files.map((file: string) => (
    <TableRow key={file}>
      <TableCell>{file}</TableCell>
    </TableRow>
  ));

  return (
    <>
      <Label>{props.label ?? "Browse and select file(s)..."}</Label>
      <Input type="text" value={props.path} className="mt-3" />
      <div
        className="mt-2 overflow-y-auto w-full border"
        style={{ height: "14rem" }}
      >
        <Table>{fileRows}</Table>
      </div>
      <div className="mt-3 flex items-center space-x-3">
        <Button>Select</Button>
        <Button variant="secondary">Cancel</Button>
        <Label className="mb-1">No file(s) selected</Label>
      </div>
    </>
  );
};

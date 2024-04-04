/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Table, TableCell, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { createPlugin } from "../core/builder";
import { useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { rpc } from "../core/rpc";
import { Checkbox } from "@/components/ui/checkbox";

/**
 * Arguments for a file browser component.
 *
 * @param initialPath - the path to display on component render
 * @param filetypes - filter directory lists by file types
 * @param multiple - whether to allow the user to select multiple files
 * @param label - label for the file browser
 * @param restrictNavigation - whether to prevent the user from accessing
 * directories outside the set path
 */
interface Data {
  initialPath: string;
  filetypes: string[];
  multiple: boolean;
  label: string | null;
  restrictNavigation: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  list_directory: (req: { path: string; filetypes: string[] }) => Promise<{
    files: string[];
  }>;
};

type S = string[];

export const FileBrowserPlugin = createPlugin<S>("marimo-file-browser")
  .withData(
    z.object({
      initialPath: z.string(),
      filetypes: z.array(z.string()),
      multiple: z.boolean(),
      label: z.string().nullable(),
      restrictNavigation: z.boolean(),
    }),
  )
  .withFunctions<PluginFunctions>({
    list_directory: rpc
      .input(
        z.object({
          path: z.string(),
          filetypes: z.array(z.string()),
        }),
      )
      .output(
        z.object({
          files: z.array(z.string()),
        }),
      ),
  })
  .renderer((props) => (
    <FileBrowser
      {...props.data}
      {...props.functions}
      value={props.value}
      setValue={props.setValue}
    />
  ));

/**
 * @param value - array of selected (filename, path) tuples
 * @param setValue - sets selected files as component value
 */
interface FileBrowserProps extends Data, PluginFunctions {
  value: S;
  setValue: (value: S) => void;
}

export const FileBrowser = ({
  value,
  setValue,
  initialPath,
  filetypes,
  multiple,
  label,
  restrictNavigation,
  list_directory,
}: FileBrowserProps): JSX.Element => {
  const [path, setPath] = useState(initialPath);

  const { data, loading, error } = useAsyncData(
    () =>
      list_directory({
        path: path,
        filetypes: filetypes,
      }),
    [path],
  );

  let { files } = data || {};
  if (files === undefined) {
    files = [];
  }

  console.log(data);
  console.log(loading);
  console.log(error);

  function setNewPath(path: string) {
    const outsideInitialPath = path.length < initialPath.length;
    if (restrictNavigation && outsideInitialPath) return;
    setPath(path);
  }

  function selectFile(file: string) {
    let filePath = path;
    if (path.slice(-1) !== "/") filePath += "/";
    filePath += file;

    // TODO: Figure out how to read checked state
    // instead of inferring selection / de-selection
    if (!multiple) {
      const newValue = [filePath];

      if (newValue === value) {
        setValue([]);
      } else {
        setValue(newValue);
      }
    } else {
      const index = value.indexOf(filePath);

      if (index == -1) {
        value.push(filePath);
      } else {
        value.splice(index, 1);
      }

      setValue(value);
    }
  }

  const fileRows = files.map((file: string) => (
    <TableRow key={file}>
      <TableCell>
        <Checkbox onClick={() => selectFile(file)} />
      </TableCell>
      <TableCell>{file}</TableCell>
    </TableRow>
  ));

  return (
    <>
      <Label>{label ?? "Browse and select file(s)..."}</Label>
      <Input
        type="text"
        value={path}
        className="mt-3"
        onChange={(e) => setNewPath(e.target.value)}
      />
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

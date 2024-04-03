/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Table, TableCell, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { createPlugin } from "../core/builder";
import { useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { useAsyncData } from "@/hooks/useAsyncData";
import { rpc } from "../core/rpc";

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
  initialPath: string;
  files: string[];
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
      files: z.array(z.string()),
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
  initialPath,
  files,
  filetypes,
  multiple,
  label,
  restrictNavigation,
  list_directory,
}: FileBrowserProps): JSX.Element => {
  const [path, setPath] = useState(initialPath);
  const [debouncedPath] = useDebounce(path, 300);

  const { data, loading, error } = useAsyncData(
    () =>
      list_directory({
        path: path,
        filetypes: filetypes,
      }),
    [debouncedPath],
  );

  console.log(data);
  console.log(loading);
  console.log(error);

  const fileRows = files.map((file: string) => (
    <TableRow key={file}>
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
        onChange={(e) => setPath(e.target.value)}
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

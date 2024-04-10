/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Table, TableCell, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { createPlugin } from "../core/builder";
import { useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { rpc } from "../core/rpc";
import { Checkbox } from "@/components/ui/checkbox";
import { Folder } from "lucide-react";

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

/**
 * @param id - File id
 * @param path - File path
 * @param name - File name
 * @param is_directory - Whether file is a directory or not
 * @param is_marimo_file - Whether file is a marimo file or not
 */
interface FileInfo {
  id: string;
  path: string;
  name: string;
  is_directory: boolean;
  is_marimo_file: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  list_directory: (req: { path: string; filetypes: string[] }) => Promise<{
    files: FileInfo[];
  }>;
};

type S = FileInfo[];

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
          files: z.array(
            z.object({
              id: z.string(),
              path: z.string(),
              name: z.string(),
              is_directory: z.boolean(),
              is_marimo_file: z.boolean(),
            }),
          ),
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

  const selectedPaths = new Set(value.map((x) => x.path));

  console.log(data);
  console.log(loading);
  console.log(error);

  function setNewPath(newPath: string) {
    // Navigate to parent directory
    if (newPath === "..") {
      newPath = path.endsWith("/") ? path.slice(0, -1) : path;
      newPath = newPath.substring(0, newPath.lastIndexOf("/"));
    }

    // If restricting navigation, check if path is outside bounds
    const outsideInitialPath = newPath.length < initialPath.length;
    if (restrictNavigation && outsideInitialPath) {
      return;
    }

    setPath(newPath);
  }

  const selectFile = (path: string, name: string) => {
    const fileInfo: FileInfo = {
      id: path,
      name: name,
      path: path,
      is_directory: false,
      is_marimo_file: false,
    };

    if (multiple) {
      if (selectedPaths.has(path)) {
        setValue(value.filter((x) => x.path !== path));
      } else {
        setValue([...value, fileInfo]);
      }
    } else {
      setValue([fileInfo]);
    }
  };

  const fileRows = [];

  fileRows.push(
    <TableRow key={"Parent directory"} onClick={() => setNewPath("..")}>
      <TableCell className="w-1/12"></TableCell>
      <TableCell className="w-11/12">..</TableCell>
    </TableRow>,
  );

  for (const file of files) {
    let filePath = path;
    if (!path.endsWith("/")) {
      filePath += "/";
    }
    filePath += file.name;

    const handleClick = file.is_directory ? setNewPath : selectFile;

    fileRows.push(
      <TableRow key={filePath} onClick={() => handleClick(filePath, file.name)}>
        <TableCell className="w-1/12">
          {file.is_directory ? (
            <Folder size={16} className="ml-2" />
          ) : (
            <Checkbox className="ml-2" checked={selectedPaths.has(filePath)} />
          )}
        </TableCell>
        <TableCell className="w-11/12">{file.name}</TableCell>
      </TableRow>,
    );
  }

  const selectedFiles = value.map((x) => <li key={x.path}>{x.path}</li>);

  return (
    <section>
      <span className="markdown">
        <strong>{label ?? "Browse and select file(s)..."}</strong>
      </span>
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
        <Table className="cursor-pointer table-fixed">{fileRows}</Table>
      </div>
      <aside className="mt-4">
        {value.length > 0 ? (
          <span className="markdown">
            <strong>{value.length} file(s) selected</strong>
            <ul style={{ margin: 0 }}>{selectedFiles}</ul>
          </span>
        ) : null}
      </aside>
    </section>
  );
};

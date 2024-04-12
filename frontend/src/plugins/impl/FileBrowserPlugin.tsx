/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Table, TableCell, TableRow } from "@/components/ui/table";
import { createPlugin } from "../core/builder";
import { useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { rpc } from "../core/rpc";
import { toast } from "@/components/ui/use-toast";
import { NativeSelect } from "@/components/ui/native-select";
import {
  FILE_TYPE_ICONS,
  FileType,
  guessFileType,
} from "@/components/editor/file-tree/types";
import { renderHTML } from "../core/RenderHTML";
import { PathBuilder, Paths } from "@/utils/paths";
import { CornerLeftUp } from "lucide-react";

/**
 * Arguments for a file browser component.
 */
interface Data {
  /** @param initialPath - the path to display on component render */
  initialPath: string;
  /** @param filetypes - filter directory lists by file types */
  filetypes: string[];
  /** @param multiple - whether to allow the user to select multiple files */
  multiple: boolean;
  /** @param label - label for the file browser */
  label: string | null;
  /**
   * @param restrictNavigation - whether to prevent the user from accessing
   * directories outside the initial path
   */
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
  list_directory: (req: { path: string }) => Promise<{
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
  multiple,
  label,
  restrictNavigation,
  list_directory,
}: FileBrowserProps): JSX.Element | null => {
  const [path, setPath] = useState(initialPath);

  const { data, loading, error } = useAsyncData(
    () =>
      list_directory({
        path: path,
      }),
    [path],
  );

  if (error) {
    console.error(error);
    toast({
      title: `Could not load files in directory ${path}`,
      description: error.message,
      variant: "danger",
    });
  }

  if (loading && !data) {
    return null;
  }

  let { files } = data || {};
  if (files === undefined) {
    files = [];
  }

  // For checkbox logic
  const selectedPaths = new Set(value.map((x) => x.path));

  // For displaying selected files
  const selectedFiles = value.map((x) => <li key={x.id}>{x.path}</li>);

  /**
   * Set new path from user input or selection.
   * @param {string} newPath - New path
   */
  function setNewPath(newPath: string) {
    // Navigate to parent directory
    if (newPath === "..") {
      newPath = Paths.dirname(path);
    }

    // If restricting navigation, check if path is outside bounds
    const outsideInitialPath = newPath.length < initialPath.length;
    if (restrictNavigation && outsideInitialPath) {
      toast({
        title: "Access denied",
        description:
          "Access to directories outside initial path is restricted.",
        variant: "danger",
      });
      return;
    }

    setPath(newPath);
  }

  /**
   * Handles file selection.
   * @param {string} path - Path of selected file
   * @param {string} name - Name of selected file
   */
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

  // Create rows for directories and files
  const fileRows = [];

  // Parent directory ".." row button
  fileRows.push(
    <TableRow
      className="hover:bg-primary hover:bg-opacity-25"
      key={"Parent directory"}
      onClick={() => setNewPath("..")}
    >
      <TableCell className="w-1/12">
        <CornerLeftUp className="ml-2" size={16} />
      </TableCell>
      <TableCell className="w-11/12">..</TableCell>
    </TableRow>,
  );

  const delimiter = path.includes("/") ? "/" : "\\";
  const pathBuilder = new PathBuilder(delimiter);

  for (const file of files) {
    const filePath = pathBuilder.join(path, file.name);

    // Click handler
    const handleClick = file.is_directory ? setNewPath : selectFile;

    // Table row styles
    const isSelected = selectedPaths.has(filePath);

    const tableRowStyles = isSelected
      ? "bg-primary bg-opacity-25 hover:bg-primary hover:bg-opacity-50"
      : "hover:bg-primary hover:bg-opacity-25";

    // Icon
    const fileType: FileType = file.is_directory
      ? "directory"
      : guessFileType(file.name);

    const Icon = FILE_TYPE_ICONS[fileType];

    fileRows.push(
      <TableRow
        key={file.id}
        className={tableRowStyles}
        onClick={() => handleClick(filePath, file.name)}
      >
        <TableCell className="w-1/12">
          <Icon size={16} className="ml-2" />
        </TableCell>
        <TableCell className="w-11/12">{file.name}</TableCell>
      </TableRow>,
    );
  }

  // Get list of parent directories
  const directories = path.split(delimiter).filter((x) => x !== "");
  directories.push(path);

  const parentDirectories = directories.map((dir, index) => {
    const dirList = directories.slice(0, index);
    return `/${dirList.join(delimiter)}`;
  });

  parentDirectories.reverse();

  label = label ?? "Browse and select file(s)...";

  return (
    <section>
      <span className="markdown">
        <strong>{renderHTML({ html: label })}</strong>
      </span>
      <NativeSelect
        className="mt-3 w-full"
        placeholder={path}
        value={path}
        onChange={(e) => setNewPath(e.target.value)}
      >
        {parentDirectories.map((dir) => (
          <option value={dir} key={dir} selected={dir === path}>
            {dir}
          </option>
        ))}
      </NativeSelect>
      <div
        className="mt-3 overflow-y-auto w-full border"
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

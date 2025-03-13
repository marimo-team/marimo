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
  type FileType,
  guessFileType,
} from "@/components/editor/file-tree/types";
import { renderHTML } from "../core/RenderHTML";
import { type FilePath, PathBuilder, Paths } from "@/utils/paths";
import { CornerLeftUp } from "lucide-react";
import { Logger } from "@/utils/Logger";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/cn";
import { Label } from "@/components/ui/label";
import { PluralWords } from "@/utils/pluralize";
import { useInternalStateWithSync } from "@/hooks/useInternalStateWithSync";

/**
 * Arguments for a file browser component.
 *
 * @param initialPath - the path to display on component render
 * @param filetypes - filetype filter
 * @param selectionMode - permit selection of files or directories
 * @param multiple - whether to allow the user to select multiple files
 * @param label - label for the file browser
 * @param restrictNavigation - whether to prevent user from accessing
 * directories outside the initial path
 */
interface Data {
  initialPath: string;
  filetypes: string[];
  selectionMode: string;
  multiple: boolean;
  label: string | null;
  restrictNavigation: boolean;
}

/**
 * File object.
 *
 * @param id - File id
 * @param path - File path
 * @param name - File name
 * @param is_directory - Whether file is a directory or not
 */
interface FileInfo {
  id: string;
  path: string;
  name: string;
  is_directory: boolean;
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
      selectionMode: z.string(),
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

const PARENT_DIRECTORY = "..";

/**
 * @param value - array of selected (filename, path) tuples
 * @param setValue - sets selected files as component value
 */
interface FileBrowserProps extends Data, PluginFunctions {
  value: S;
  setValue: (value: S) => void;
}

/**
 * File browser component.
 *
 * Only works for absolute paths.
 */
export const FileBrowser = ({
  value,
  setValue,
  initialPath,
  selectionMode,
  multiple,
  label,
  restrictNavigation,
  list_directory,
}: FileBrowserProps): JSX.Element | null => {
  const [path, setPath] = useInternalStateWithSync(initialPath);
  const [selectAllLabel, setSelectAllLabel] = useState("Select all");
  const [isUpdatingPath, setIsUpdatingPath] = useState(false);

  const { data, loading, error } = useAsyncData(
    () =>
      list_directory({
        path: path,
      }),
    [path],
  );

  if (error) {
    Logger.error(error);
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

  const pathBuilder = PathBuilder.guessDeliminator(initialPath);
  const delimiter = pathBuilder.deliminator;

  const selectedPaths = new Set(value.map((x) => x.path));
  const selectedFiles = value.map((x) => <li key={x.id}>{x.path}</li>);

  const canSelectDirectories =
    selectionMode === "directory" || selectionMode === "all";
  const canSelectFiles = selectionMode === "file" || selectionMode === "all";

  function setNewPath(newPath: string) {
    // Prevent updating path while updating
    if (isUpdatingPath) {
      return;
    }
    // Set updating flag
    setIsUpdatingPath(true);

    // Navigate to parent directory
    if (newPath === PARENT_DIRECTORY) {
      if (path === delimiter) {
        setIsUpdatingPath(false);
        return;
      }

      newPath = Paths.dirname(path);

      if (newPath === "") {
        newPath = delimiter;
      }
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
      setIsUpdatingPath(false);
      return;
    }

    // Update path and reset select all label
    setPath(newPath);
    setSelectAllLabel("Select all");
    setIsUpdatingPath(false);
  }

  function createFileInfo(
    path: string,
    name: string,
    isDirectory: boolean,
  ): FileInfo {
    return {
      id: path,
      name: name,
      path: path,
      is_directory: isDirectory,
    };
  }

  function handleSelection(path: string, name: string, isDirectory: boolean) {
    const fileInfo = createFileInfo(path, name, isDirectory);

    if (multiple) {
      if (selectedPaths.has(path)) {
        setValue(value.filter((x) => x.path !== path));
        setSelectAllLabel("Select all");
      } else {
        setValue([...value, fileInfo]);
      }
    } else {
      setValue([fileInfo]);
    }
  }

  function deselectAllFiles() {
    setValue(value.filter((x) => Paths.dirname(x.path) !== path));
    setSelectAllLabel("Select all");
  }

  function selectAllFiles() {
    if (!files) {
      return;
    }

    const filesInView: FileInfo[] = [];

    for (const file of files) {
      if (!canSelectDirectories && file.is_directory) {
        continue;
      }
      if (selectedPaths.has(file.path)) {
        continue;
      }
      const fileInfo = createFileInfo(file.path, file.name, file.is_directory);
      filesInView.push(fileInfo);
    }

    setValue([...value, ...filesInView]);
    setSelectAllLabel("Deselect all");
  }

  // Create rows for directories and files
  const fileRows: React.ReactNode[] = [];

  // Parent directory ".." row button
  fileRows.push(
    <TableRow
      className="hover:bg-primary hover:bg-opacity-25 select-none"
      key={"Parent directory"}
      onClick={() => setNewPath(PARENT_DIRECTORY)}
    >
      <TableCell className="w-[50px] pl-4">
        <CornerLeftUp size={16} />
      </TableCell>
      <TableCell>{PARENT_DIRECTORY}</TableCell>
    </TableRow>,
  );

  for (const file of files) {
    let filePath = file.path;

    if (filePath.startsWith("//")) {
      filePath = filePath.slice(1) as FilePath;
    }

    // Click handler
    const handleClick = file.is_directory ? setNewPath : handleSelection;

    // Icon
    const fileType: FileType = file.is_directory
      ? "directory"
      : guessFileType(file.name);

    const Icon = FILE_TYPE_ICONS[fileType];

    const isSelected = selectedPaths.has(filePath);
    const renderCheckboxOrIcon = () => {
      if (
        (canSelectDirectories && file.is_directory) ||
        (canSelectFiles && !file.is_directory)
      ) {
        return (
          <>
            <Checkbox
              checked={isSelected}
              onClick={(e) => {
                handleSelection(filePath, file.name, file.is_directory);
                e.stopPropagation();
              }}
              className={cn("", {
                "hidden group-hover:flex": !isSelected,
              })}
            />
            <Icon
              size={16}
              className={cn("mr-2", {
                hidden: isSelected,
                "group-hover:hidden": !isSelected,
              })}
            />
          </>
        );
      }

      return <Icon size={16} className="mr-2" />;
    };

    fileRows.push(
      <TableRow
        key={file.id}
        className={cn(
          "hover:bg-primary hover:bg-opacity-25 group select-none",
          {
            "bg-primary bg-opacity-25": isSelected,
          },
        )}
        onClick={() => handleClick(filePath, file.name, file.is_directory)}
      >
        <TableCell className="w-[50px] pl-4">
          {renderCheckboxOrIcon()}
        </TableCell>
        <TableCell>{file.name}</TableCell>
      </TableRow>,
    );
  }

  // Get list of parent directories.
  //
  // Assumes that path contains at least one delimiter, which is true
  // only if this is an absolute path.
  const protocolMatch = path.match(/^[A-Za-z]+:\/\//);
  const protocol = protocolMatch ? protocolMatch[0] : "/";
  const pathWithoutProtocol = protocol ? path.slice(protocol.length) : path;

  const directories = pathWithoutProtocol
    .split(delimiter)
    .filter((x) => x !== "");
  directories.push(pathWithoutProtocol);

  let parentDirectories = directories.map((dir, index) => {
    const dirList = directories.slice(0, index);
    return `${protocol}${dirList.join(delimiter)}`;
  });

  if (restrictNavigation) {
    parentDirectories = parentDirectories.filter((x) =>
      x.startsWith(initialPath),
    );
  }
  parentDirectories.reverse();

  const selectionKindLabel =
    selectionMode === "all"
      ? PluralWords.of("file", "folder")
      : selectionMode === "directory"
        ? PluralWords.of("folder")
        : PluralWords.of("file");

  const renderHeader = () => {
    label = label ?? `Select ${selectionKindLabel.join(" and ", 2)}...`;
    const labelText = <Label>{renderHTML({ html: label })}</Label>;

    if (multiple) {
      return (
        <div className="grid grid-cols-2 items-center border-1">
          <div className="justify-self-start mb-1">{labelText}</div>
          <div className="justify-self-end">
            <Button
              size="xs"
              variant="link"
              className="w-full"
              onClick={
                selectAllLabel === "Select all"
                  ? () => selectAllFiles()
                  : () => deselectAllFiles()
              }
            >
              {renderHTML({ html: selectAllLabel })}
            </Button>
          </div>
        </div>
      );
    }

    return labelText;
  };

  return (
    <div>
      {renderHeader()}
      <NativeSelect
        className="mt-2 w-full"
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
      <div className="mt-4">
        {value.length > 0 && (
          <>
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs">
                {value.length} {selectionKindLabel.join(" or ", value.length)}{" "}
                selected
              </span>
              <button
                className={cn(
                  "text-xs text-destructive hover:underline cursor-pointer",
                )}
                onClick={() => setValue([])}
              >
                clear all
              </button>
            </div>
            <div className="markdown">
              <ul
                style={{ marginBlock: 0 }}
                className="m-0 text-xs text-muted-foreground"
              >
                {selectedFiles}
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

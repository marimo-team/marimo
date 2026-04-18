/* Copyright 2026 Marimo. All rights reserved. */

import { type LucideIcon, CornerLeftUp } from "lucide-react";
import { type JSX, useEffect, useState } from "react";
import { z } from "zod";
import {
  FILE_ICON as FILE_TYPE_ICONS,
  type FileIconType as FileType,
  guessFileIconType as guessFileType,
} from "@/components/editor/file-tree/file-icons";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { RANDOM_ID_ATTR } from "@/core/dom/ui-element-constants";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInternalStateWithSync } from "@/hooks/useInternalStateWithSync";
import { cn } from "@/utils/cn";
import { type FilePath, PathBuilder, Paths } from "@/utils/paths";
import { getProtocolAndParentDirectories } from "@/utils/pathUtils";
import { PluralWords } from "@/utils/pluralize";
import { createPlugin } from "../core/builder";
import { renderHTML } from "../core/RenderHTML";
import { rpc } from "../core/rpc";
import { Banner } from "./common/error-banner";

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

// oxlint-disable-next-line typescript/consistent-type-definitions
type PluginFunctions = {
  list_directory: (req: { path: string }) => Promise<{
    files: FileInfo[];
    total_count: number;
    is_truncated: boolean;
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
          total_count: z.number(),
          is_truncated: z.boolean(),
        }),
      ),
  })
  .renderer((props) => (
    <FileBrowser
      {...props.data}
      {...props.functions}
      host={props.host}
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
  host: HTMLElement;
}

interface CheckboxOrIconProps {
  isSelected: boolean;
  canSelect: boolean;
  Icon: LucideIcon;
  onSelect: () => void;
}

function CheckboxOrIcon({
  isSelected,
  canSelect,
  Icon,
  onSelect,
}: CheckboxOrIconProps) {
  if (canSelect) {
    return (
      <>
        <Checkbox
          checked={isSelected}
          onClick={(e) => {
            onSelect();
            e.stopPropagation();
          }}
          className={cn({ "hidden group-hover:flex": !isSelected })}
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
  host,
}: FileBrowserProps): JSX.Element | null => {
  const [path, setPath] = useInternalStateWithSync(initialPath);
  const [isUpdatingPath, setIsUpdatingPath] = useState(false);
  const [showLoadingOverlay, setShowLoadingOverlay] = useState(false);

  // HACK: use the random-id of the host element to force a re-render
  // when the random-id changes, this means the cell was re-rendered
  const randomId = host
    .closest(`[${RANDOM_ID_ATTR}]`)
    ?.getAttribute(RANDOM_ID_ATTR);

  const { data, error, isPending } = useAsyncData(() => {
    return list_directory({ path: path });
  }, [path, randomId]);

  useEffect(() => {
    if (!isPending) {
      setShowLoadingOverlay(false);
      return;
    }

    const timeout = window.setTimeout(() => {
      setShowLoadingOverlay(true);
    }, 200);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [isPending]);

  const files = data?.files ?? [];
  const selectedPaths = new Set(value.map((x) => x.path));
  const canSelectDirectories =
    selectionMode === "directory" || selectionMode === "all";
  const canSelectFiles = selectionMode === "file" || selectionMode === "all";

  const selectable = files.filter(
    (f) =>
      (canSelectDirectories && f.is_directory) ||
      (canSelectFiles && !f.is_directory),
  );
  const allSelected =
    selectable.length > 0 && selectable.every((f) => selectedPaths.has(f.path));

  if (!data && error) {
    return <Banner kind="danger">{error.message}</Banner>;
  }

  const pathBuilder = PathBuilder.guessDeliminator(initialPath);
  const delimiter = pathBuilder.deliminator;

  const selectedFiles = value.map((x) => <li key={x.id}>{x.path}</li>);

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

    setPath(newPath);
    setIsUpdatingPath(false);
  }

  function createFileInfo({
    path,
    name,
    isDirectory,
  }: {
    path: string;
    name: string;
    isDirectory: boolean;
  }): FileInfo {
    return {
      id: path,
      name: name,
      path: path,
      is_directory: isDirectory,
    };
  }

  function handleSelection({
    path,
    name,
    isDirectory,
  }: {
    path: string;
    name: string;
    isDirectory: boolean;
  }) {
    const fileInfo = createFileInfo({ path, name, isDirectory });

    if (selectedPaths.has(path)) {
      setValue(value.filter((x) => x.path !== path));
    } else {
      setValue(multiple ? [...value, fileInfo] : [fileInfo]);
    }
  }

  function deselectAllFiles() {
    setValue(value.filter((x) => Paths.dirname(x.path) !== path));
  }

  function selectAllFiles() {
    const filesInView: FileInfo[] = [];

    for (const file of files) {
      if (!canSelectDirectories && file.is_directory) {
        continue;
      }
      if (selectedPaths.has(file.path)) {
        continue;
      }
      const fileInfo = createFileInfo({
        path: file.path,
        name: file.name,
        isDirectory: file.is_directory,
      });
      filesInView.push(fileInfo);
    }

    setValue([...value, ...filesInView]);
  }

  // Create rows for directories and files
  const fileRows: React.ReactNode[] = [];

  // Parent directory ".." row button
  fileRows.push(
    <TableRow
      className="hover:bg-accent select-none"
      key="Parent directory"
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

    const isSelectable =
      (canSelectDirectories && file.is_directory) ||
      (canSelectFiles && !file.is_directory);

    const fileType: FileType = file.is_directory
      ? "directory"
      : guessFileType(file.name);

    const Icon = FILE_TYPE_ICONS[fileType];

    const isSelected = selectedPaths.has(filePath);

    fileRows.push(
      <TableRow
        key={file.id}
        className={cn("hover:bg-accent group select-none", {
          "bg-primary/25 hover:bg-primary/35": isSelected,
          "cursor-default": !isSelectable && !file.is_directory,
        })}
        onClick={() => {
          if (isSelectable) {
            handleSelection({
              path: filePath,
              name: file.name,
              isDirectory: file.is_directory,
            });
          }
        }}
        onDoubleClick={() => {
          if (file.is_directory) {
            setNewPath(filePath);
          }
        }}
      >
        <TableCell className="w-[50px] pl-4">
          <CheckboxOrIcon
            isSelected={isSelected}
            canSelect={isSelectable}
            Icon={Icon}
            onSelect={() =>
              handleSelection({
                path: filePath,
                name: file.name,
                isDirectory: file.is_directory,
              })
            }
          />
        </TableCell>
        <TableCell>{file.name}</TableCell>
      </TableRow>,
    );
  }

  // Get list of parent directories.
  //
  // Assumes that path contains at least one delimiter, which is true
  // only if this is an absolute path.
  const { parentDirectories } = getProtocolAndParentDirectories({
    path,
    delimiter,
    initialPath,
    restrictNavigation,
  });

  const selectionKindLabel =
    selectionMode === "all"
      ? PluralWords.of("file", "folder")
      : selectionMode === "directory"
        ? PluralWords.of("folder")
        : PluralWords.of("file");

  const renderHeader = () => {
    const displayLabel =
      label ?? `Select ${selectionKindLabel.join(" and ", 2)}...`;
    const labelText = <Label>{renderHTML({ html: displayLabel })}</Label>;

    if (multiple) {
      return (
        <div className="flex items-center justify-between border px-2">
          <div className="mb-1">{labelText}</div>
          <div>
            <Button
              size="xs"
              variant="link"
              onClick={allSelected ? deselectAllFiles : selectAllFiles}
            >
              {allSelected ? "Deselect all" : "Select all"}
            </Button>
          </div>
        </div>
      );
    }

    return labelText;
  };

  return (
    <div>
      {error && <Banner kind="danger">{error.message}</Banner>}
      {renderHeader()}
      <NativeSelect
        className="mt-2 w-full"
        placeholder={path}
        value={path}
        onChange={(e) => setNewPath(e.target.value)}
      >
        {parentDirectories.map((dir) => (
          <option value={dir} key={dir}>
            {dir}
          </option>
        ))}
      </NativeSelect>

      {data && typeof data.total_count === "number" && (
        <div className="text-xs text-muted-foreground mt-1 px-1">
          {data.is_truncated
            ? `Showing ${files.length} of ${data.total_count} items`
            : `${data.total_count} ${data.total_count === 1 ? "item" : "items"}`}
        </div>
      )}

      <div
        className="mt-3 overflow-y-auto w-full border relative"
        style={{ height: "14rem" }}
        aria-busy={isPending}
        aria-live="polite"
      >
        {showLoadingOverlay && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-background/80 text-xs text-muted-foreground pointer-events-none z-10"
            role="status"
          >
            <Spinner size="small" />
            <span>Listing files...</span>
          </div>
        )}
        <Table className="cursor-pointer table-fixed">
          <TableBody>{fileRows}</TableBody>
        </Table>
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
                className={cn("text-xs text-destructive hover:underline")}
                onClick={() => setValue([])}
                type="button"
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

/* Copyright 2026 Marimo. All rights reserved. */

import { CopyIcon, Edit3Icon, Trash2Icon } from "lucide-react";
import type React from "react";
import { useCallback } from "react";
import type { NodeApi } from "react-arborist";
import useEvent from "react-use-event-hook";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/use-toast";
import { useRequestClient } from "@/core/network/requests";
import type { FileInfo, FileUpdateResponse } from "@/core/network/types";
import {
  makeDuplicateName,
  resolvePaths,
  toAbsolutePath,
} from "@/utils/pathUtils";
import { MENU_ITEM_ICON_CLASS, MoreActionsButton } from "./tree-actions";

export function handleFileResponse(
  response: FileUpdateResponse,
): FileUpdateResponse | null {
  if (!response.success) {
    toast({
      title: "Failed",
      description: response.message,
    });
    return null;
  }
  return response;
}

/**
 * Result of a successful file operation; `null` means the server rejected
 * the request and a toast was already shown.
 */
export type FileOperationResult = FileUpdateResponse | null;

/**
 * Hook that exposes rename / duplicate / delete operations against absolute
 * paths, handling path resolution (via `resolvePaths`) and error toasting.
 *
 * `root` is the workspace / tree root used to turn relative node paths into
 * absolute paths for the API. Pass `""` if all node paths are already
 * absolute (in which case `resolvePaths` is a no-op transformation).
 */
export function useFileOperations({ root }: { root: string }) {
  const {
    sendRenameFileOrFolder,
    sendCopyFileOrFolder,
    sendDeleteFileOrFolder,
  } = useRequestClient();

  const renameFile = useCallback(
    async (
      file: Pick<FileInfo, "path">,
      newName: string,
    ): Promise<FileOperationResult> => {
      const { path, newPath } = resolvePaths({
        path: file.path,
        name: newName,
        root,
      });
      const resp = await sendRenameFileOrFolder({ path, newPath });
      return handleFileResponse(resp);
    },
    [root, sendRenameFileOrFolder],
  );

  const duplicateFile = useCallback(
    async (
      file: Pick<FileInfo, "path" | "name">,
    ): Promise<FileOperationResult> => {
      const { path, newPath } = resolvePaths({
        path: file.path,
        name: makeDuplicateName(file.name),
        root,
      });
      const resp = await sendCopyFileOrFolder({ path, newPath });
      return handleFileResponse(resp);
    },
    [root, sendCopyFileOrFolder],
  );

  const deleteFile = useCallback(
    async (file: Pick<FileInfo, "path">): Promise<FileOperationResult> => {
      const resp = await sendDeleteFileOrFolder({
        path: toAbsolutePath(file.path, root),
      });
      return handleFileResponse(resp);
    },
    [root, sendDeleteFileOrFolder],
  );

  return { renameFile, duplicateFile, deleteFile };
}

export function useConfirmDeleteFile() {
  const { openConfirm } = useImperativeModal();

  return useCallback(
    (name: string, onConfirm: () => void | Promise<void>) => {
      openConfirm({
        title: "Delete notebook",
        description: `Are you sure you want to delete ${name}?`,
        confirmAction: (
          <AlertDialogDestructiveAction
            onClick={async () => {
              await onConfirm();
            }}
            aria-label="Confirm"
          >
            Delete
          </AlertDialogDestructiveAction>
        ),
      });
    },
    [openConfirm],
  );
}

/**
 * High-level handlers for rename/duplicate/delete against a single node
 *
 * All successful operations fire `onAfterChange` so callers can refresh their
 * data sources (workspace tree + recent notebooks on the homepage).
 */
export function useNotebookFileActions({
  node,
  root,
  onAfterChange,
}: {
  node: NodeApi<FileInfo>;
  root: string;
  onAfterChange?: () => void;
}) {
  const { duplicateFile, deleteFile } = useFileOperations({ root });
  const confirmDelete = useConfirmDeleteFile();

  const handleRename = useEvent(() => {
    node.edit();
  });

  const handleDuplicate = useEvent(async () => {
    const result = await duplicateFile(node.data);
    if (result) {
      onAfterChange?.();
    }
  });

  const handleDelete = useEvent(() => {
    confirmDelete(node.data.name, async () => {
      const result = await deleteFile(node.data);
      if (result) {
        onAfterChange?.();
      }
    });
  });

  return { handleRename, handleDuplicate, handleDelete };
}

export const FileActionsDropdown = ({
  testId,
  buttonClassName,
  iconClassName,
  contentClassName,
  preventDefaultOnTrigger = false,
  children,
}: {
  testId?: string;
  buttonClassName?: string;
  iconClassName?: string;
  contentClassName?: string;
  /**
   * When true, the trigger also calls `preventDefault()` on click — needed
   * when the dropdown is nested inside an `<a>` or other element whose
   * default click behavior (navigation, submit, etc.) should be suppressed.
   */
  preventDefaultOnTrigger?: boolean;
  children: React.ReactNode;
}) => (
  <DropdownMenu modal={false}>
    <DropdownMenuTrigger
      asChild={true}
      tabIndex={-1}
      onClick={(e) => {
        e.stopPropagation();
        if (preventDefaultOnTrigger) {
          e.preventDefault();
        }
      }}
    >
      <MoreActionsButton
        data-testid={testId}
        className={buttonClassName}
        iconClassName={iconClassName}
      />
    </DropdownMenuTrigger>
    <DropdownMenuContent
      align="end"
      className={contentClassName ?? "print:hidden w-[220px]"}
      onClick={(e) => e.stopPropagation()}
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      {children}
    </DropdownMenuContent>
  </DropdownMenu>
);

export const RenameMenuItem = ({
  onSelect,
  disabled,
  title,
}: {
  onSelect: (evt: Event) => void;
  disabled?: boolean;
  title?: string;
}) => (
  <DropdownMenuItem onSelect={onSelect} disabled={disabled} title={title}>
    <Edit3Icon className={MENU_ITEM_ICON_CLASS} />
    Rename
  </DropdownMenuItem>
);

export const DuplicateMenuItem = ({
  onSelect,
  disabled,
  title,
}: {
  onSelect: (evt: Event) => void;
  disabled?: boolean;
  title?: string;
}) => (
  <DropdownMenuItem onSelect={onSelect} disabled={disabled} title={title}>
    <CopyIcon className={MENU_ITEM_ICON_CLASS} />
    Duplicate
  </DropdownMenuItem>
);

export const DeleteMenuItem = ({
  onSelect,
  disabled,
  title,
}: {
  onSelect: (evt: Event) => void;
  disabled?: boolean;
  title?: string;
}) => (
  <DropdownMenuItem
    onSelect={onSelect}
    variant="danger"
    disabled={disabled}
    title={title}
  >
    <Trash2Icon className={MENU_ITEM_ICON_CLASS} />
    Delete
  </DropdownMenuItem>
);

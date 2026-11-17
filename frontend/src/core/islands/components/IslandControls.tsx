/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { CopyIcon, PlayIcon } from "lucide-react";
import type { JSX } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import { runCells } from "@/core/executions";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";

/**
 * Props for IslandControls component
 */
export interface IslandControlsProps {
  /**
   * ID of the cell this control operates on
   */
  cellId: CellId;

  /**
   * Callback to get the current code for the cell
   */
  codeCallback: () => string;

  /**
   * Whether the controls should be visible
   */
  visible: boolean;
}

/**
 * Props for individual control buttons
 */
interface IconButtonProps {
  tooltip: string;
  icon: JSX.Element;
  action: () => void;
}

/**
 * A single icon button with tooltip
 */
const IconButton: React.FC<IconButtonProps> = ({ tooltip, icon, action }) => (
  <Tooltip content={tooltip} delayDuration={200}>
    <Button
      size="icon"
      variant="outline"
      className="bg-background h-5 w-5 mb-0"
      onClick={action}
    >
      {icon}
    </Button>
  </Tooltip>
);

/**
 * Controls for interacting with an island cell.
 *
 * Provides buttons to:
 * - Copy the cell's code to clipboard
 * - Re-run the cell
 */
export const IslandControls: React.FC<IslandControlsProps> = ({
  cellId,
  codeCallback,
  visible,
}) => {
  const store = useStore();
  const model = useAtomValue(activeDocumentModelAtom);

  const handleCopy = () => {
    copyToClipboard(codeCallback());
  };

  // The island's editor is a UI element, so its code reaches the document
  // here rather than through an editor binding.
  const handleRun = async () => {
    if (model === null) {
      return;
    }
    const code = codeCallback();
    try {
      store.set(model.editAtom, (tx) => tx.setCode(cellId, code));
    } catch (error) {
      Logger.error("The island's cell is not in the document", error);
      return;
    }
    await runCells(store, [cellId]);
  };

  return (
    <div
      className="absolute top-0 right-0 z-50 flex items-center justify-center gap-1"
      style={{ display: visible ? "flex" : "none" }}
    >
      <IconButton
        tooltip="Copy code"
        icon={<CopyIcon className="size-3" />}
        action={handleCopy}
      />
      <IconButton
        tooltip="Re-run cell"
        icon={<PlayIcon className="size-3" />}
        action={handleRun}
      />
    </div>
  );
};

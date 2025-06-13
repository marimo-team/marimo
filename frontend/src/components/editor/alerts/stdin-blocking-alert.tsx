/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import { Logger } from "@/utils/Logger";
import { Button } from "../../ui/button";
import { Kbd } from "../../ui/kbd";
import { FloatingAlert } from "./floating-alert";

// Atom to check if there is a cell with unresolved stdin
const hasBlockingStdinAtom = atom((get) => {
  const notebook = get(notebookAtom);

  // Check each cell in order
  for (const cellId of notebook.cellIds.inOrderIds) {
    // Check if the cell is idle and has unresolved stdin
    const runtime = notebook.cellRuntime[cellId];
    if (runtime.status === "idle") {
      const hasUnresolvedStdin = runtime.consoleOutputs.some(
        (output) => output.channel === "stdin" && output.response === undefined,
      );
      if (hasUnresolvedStdin) {
        return true;
      }
    }
  }

  return false;
});

export const StdinBlockingAlert: React.FC = () => {
  const hasBlockingStdin = useAtomValue(hasBlockingStdinAtom);

  const handleJumpToStdin = () => {
    const el = document.querySelector<HTMLElement>("[data-stdin-blocking]");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      requestAnimationFrame(() => {
        el.focus();
      });
    } else {
      Logger.error("No element with data-stdin-blocking found");
    }
  };

  return (
    <FloatingAlert title="Program waiting for input" show={hasBlockingStdin}>
      <p>
        The program is still running, but blocked on{" "}
        <Kbd className="inline">stdin</Kbd>.
        <Button
          variant="link"
          className="h-auto font-normal"
          onClick={handleJumpToStdin}
        >
          Jump to the cell
        </Button>
      </p>
    </FloatingAlert>
  );
};

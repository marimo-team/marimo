/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import { Banner } from "@/plugins/impl/common/error-banner";
import { Logger } from "@/utils/Logger";
import { Button } from "../ui/button";
import { Kbd } from "../ui/kbd";
import { DelayMount } from "../utils/delay-mount";

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

  if (!hasBlockingStdin) {
    return null;
  }

  const body = (
    <div className="flex flex-col gap-4 mb-5 fixed top-5 left-1/2 transform -translate-x-1/2 z-[200] opacity-95">
      <Banner
        kind="info"
        className="flex flex-col rounded py-2 px-4 animate-in slide-in-from-top w-fit"
      >
        <div className="flex justify-between">
          <span className="font-bold text-lg flex items-center mb-1">
            Program waiting for input
          </span>
        </div>
        <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
          <div>
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
          </div>
        </div>
      </Banner>
    </div>
  );

  // Delay the mount to avoid flickering
  return <DelayMount milliseconds={2000}>{body}</DelayMount>;
};

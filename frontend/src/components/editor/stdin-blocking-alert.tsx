/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { Banner } from "@/plugins/impl/common/error-banner";
import { pendingPdbInputAtom } from "@/core/codemirror/cells/debugger-state";
import { kioskModeAtom } from "@/core/mode";
import { Logger } from "@/utils/Logger";
import { Button } from "../ui/button";
import { Kbd } from "../ui/kbd";
import { DelayMount } from "../utils/delay-mount";

export const hasBlockingStdinAtom = atom((get) => {
  if (!get(kioskModeAtom) && get(pendingPdbInputAtom) !== null) {
    return true;
  }
  const replica = get(activeNotebookReplicaAtom);
  if (replica === null) {
    return false;
  }
  for (const { record, items } of get(
    replica.executionsAtom,
  ).executions.values()) {
    if (record.status === "running") {
      for (const item of items.values()) {
        if (item.kind === "input" && item.status === "pending") {
          return true;
        }
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
    <div className="flex flex-col gap-4 mb-5 fixed top-5 left-1/2 transform -translate-x-1/2 z-200 opacity-95">
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

/* Copyright 2024 Marimo. All rights reserved. */
import { formatOutput } from "@/components/editor/Output";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { NotebookState, notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { CellRuntimeState } from "@/core/cells/types";
import { useEventListener } from "@/hooks/useEventListener";
import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { CopyIcon, Loader2Icon } from "lucide-react";
import React, { PropsWithChildren, useCallback, useState } from "react";

interface Props {
  cellId: CellId;
  code: string;
  children: React.ReactNode;
}

export const MarimoOutputWrapper: React.FC<Props> = ({
  cellId,
  code,
  children,
}) => {
  const [pressed, setPressed] = useState<boolean>(false);
  const selector = useCallback(
    (s: NotebookState) => s.cellRuntime[cellId],
    [cellId],
  );
  const runtime = useAtomValue(selectAtom(notebookAtom, selector));

  useEventListener(document, "keydown", (e) => {
    if (e.metaKey || e.ctrlKey) {
      setPressed(true);
    }
  });

  useEventListener(document, "keyup", (e) => {
    if (e.metaKey || e.ctrlKey || e.key === "Meta" || e.key === "Control") {
      setPressed(false);
    }
  });

  if (!runtime?.output) {
    return children;
  }

  return (
    <div className="relative min-h-6">
      {formatOutput({ message: runtime.output })}
      <Indicator state={runtime} />
      <div
        className="absolute top-0 right-0 z-50"
        style={{ display: pressed ? "block" : "none" }}
      >
        <Tooltip content="Copy code">
          <Button
            size="icon"
            variant="outline"
            className="bg-background h-5 w-5 mb-0"
            onClick={() => navigator.clipboard.writeText(code)}
          >
            <CopyIcon className="size-3" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
};

const Indicator: React.FC<{ state: CellRuntimeState }> = ({ state }) => {
  if (state.status === "running") {
    return (
      <DelayRender>
        <div className="absolute top-1 right-1">
          <Loader2Icon className="animate-spin size-4" />
        </div>
      </DelayRender>
    );
  }

  return null;
};

// Render delay for children 200ms, using only css
const DelayRender: React.FC<PropsWithChildren> = ({ children }) => {
  return <div className="animate-delayed-show-200">{children}</div>;
};

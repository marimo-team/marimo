/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { CopyIcon, Loader2Icon, PlayIcon } from "lucide-react";
import React, {
  type JSX,
  type PropsWithChildren,
  useCallback,
  useState,
} from "react";
import { OutputRenderer } from "@/components/editor/Output";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { CellRuntimeState } from "@/core/cells/types";
import { sendRun } from "@/core/network/requests";
import { useEventListener } from "@/hooks/useEventListener";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";

interface Props {
  cellId: CellId;
  codeCallback: () => string;
  alwaysShowRun: boolean;
  children: React.ReactNode;
}

interface IconButtonProps {
  tooltip: string;
  icon: JSX.Element;
  action: () => void;
}

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

export const MarimoOutputWrapper: React.FC<Props> = ({
  cellId,
  codeCallback,
  alwaysShowRun,
  children,
}) => {
  const [pressed, setPressed] = useState<boolean>(alwaysShowRun);
  const selector = useCallback(
    (s: NotebookState) => s.cellRuntime[cellId],
    [cellId],
  );
  const runtime = useAtomValue(selectAtom(notebookAtom, selector));

  // No need to register, if display is default.
  // Lint still wants use to have the same event listeners per instance (which
  // makes sense), so noop is used.
  const maybeNoop = (fn: (e: KeyboardEvent) => void) =>
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    alwaysShowRun ? () => {} : fn;

  useEventListener(
    document,
    "keydown",
    maybeNoop((e) => {
      if (!alwaysShowRun && (e.metaKey || e.ctrlKey)) {
        setPressed(true);
      }
    }),
  );
  useEventListener(
    document,
    "keyup",
    maybeNoop((e) => {
      if (
        !alwaysShowRun &&
        (e.metaKey || e.ctrlKey || e.key === "Meta" || e.key === "Control")
      ) {
        setPressed(false);
      }
    }),
  );
  // Set pressed to false if the window loses focus
  useEventListener(window, "blur", () => setPressed(false));
  useEventListener(window, "mouseleave", () => setPressed(false));

  if (!runtime?.output) {
    return <div className="relative min-h-6 empty:hidden">{children}</div>;
  }

  // No output to display
  // Maybe in future, we can configure this to
  // fallback to displaying the code.
  if (isOutputEmpty(runtime.output)) {
    return null;
  }

  return (
    <div className="relative min-h-6">
      <OutputRenderer message={runtime.output} />
      <Indicator state={runtime} />
      <div
        className="absolute top-0 right-0 z-50 flex items-center justify-center gap-1"
        style={{ display: pressed ? "flex" : "none" }}
      >
        <IconButton
          tooltip="Copy code"
          icon={<CopyIcon className="size-3" />}
          action={() => copyToClipboard(codeCallback())}
        />
        <IconButton
          tooltip="Re-run cell"
          icon={<PlayIcon className="size-3" />}
          action={async () => {
            await sendRun({
              cellIds: [cellId],
              codes: [codeCallback()],
            }).catch((error) => {
              Logger.error(error);
            });
          }}
        />
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

/* Copyright 2026 Marimo. All rights reserved. */
import { SquareIcon } from "lucide-react";
import type { JSX } from "react";
import { interruptRuntime } from "@/core/executions";
import { store } from "@/core/state/jotai";
import type { RuntimeState } from "@/core/network/types";
import { isAppInteractionDisabled } from "@/core/session/connection-utils";
import type { ConnectionState } from "@/core/session/types";
import { Functions } from "@/utils/functions";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { ToolbarItem } from "./toolbar";
import { useShouldShowInterrupt } from "./useShouldShowInterrupt";

export const StopButton = (props: {
  status: RuntimeState;
  connectionState: ConnectionState;
}): JSX.Element => {
  const { connectionState, status } = props;

  const running = status === "running";

  // Show the interrupt button after 200ms to avoid flickering.
  const showInterrupt = useShouldShowInterrupt(running);

  return (
    <ToolbarItem
      tooltip={renderShortcut("global.interrupt")}
      disabled={isAppInteractionDisabled(connectionState) || !showInterrupt}
      onClick={showInterrupt ? () => interruptRuntime(store) : Functions.NOOP}
      variant={showInterrupt ? "stale" : "disabled"}
      data-testid="run-button"
    >
      <SquareIcon strokeWidth={1.5} />
    </ToolbarItem>
  );
};

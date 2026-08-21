/* Copyright 2026 Marimo. All rights reserved. */
import { SquareIcon } from "lucide-react";
import type { JSX } from "react";
import type { CellExecutionPhase } from "@/core/cells/semantic-state";
import { useRequestClient } from "@/core/network/requests";
import { isAppInteractionDisabled } from "@/core/websocket/connection-utils";
import type { WebSocketState } from "@/core/websocket/types";
import { Functions } from "@/utils/functions";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { ToolbarItem } from "./toolbar";
import { useShouldShowInterrupt } from "./useShouldShowInterrupt";

export const StopButton = (props: {
  phase: CellExecutionPhase;
  connectionState: WebSocketState;
}): JSX.Element => {
  const { connectionState, phase } = props;
  const { sendInterrupt } = useRequestClient();

  const running = phase.kind === "running";

  // Show the interrupt button after 200ms to avoid flickering.
  const showInterrupt = useShouldShowInterrupt(running);

  return (
    <ToolbarItem
      tooltip={renderShortcut("global.interrupt")}
      disabled={isAppInteractionDisabled(connectionState) || !showInterrupt}
      onClick={showInterrupt ? sendInterrupt : Functions.NOOP}
      variant={showInterrupt ? "stop" : "disabled"}
      data-testid="run-button"
    >
      <SquareIcon strokeWidth={1.5} />
    </ToolbarItem>
  );
};

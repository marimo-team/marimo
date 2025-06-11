/* Copyright 2024 Marimo. All rights reserved. */
import { SquareIcon } from "lucide-react";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { sendInterrupt } from "@/core/network/requests";
import { useShouldShowInterrupt } from "./useShouldShowInterrupt";
import type { RuntimeState } from "@/core/network/types";
import { Functions } from "@/utils/functions";
import { ToolbarItem } from "./toolbar";
import type { WebSocketState } from "@/core/websocket/types";
import { isAppInteractionDisabled } from "@/core/websocket/connection-utils";

import type { JSX } from "react";

export const StopButton = (props: {
  status: RuntimeState;
  connectionState: WebSocketState;
}): JSX.Element => {
  const { connectionState, status } = props;

  const running = status === "running";

  // Show the interrupt button after 200ms to avoid flickering.
  const showInterrupt = useShouldShowInterrupt(running);

  return (
    <ToolbarItem
      tooltip={renderShortcut("global.interrupt")}
      disabled={isAppInteractionDisabled(connectionState) || !showInterrupt}
      onClick={showInterrupt ? sendInterrupt : Functions.NOOP}
      variant={showInterrupt ? "stale" : "disabled"}
      data-testid="run-button"
    >
      <SquareIcon strokeWidth={1.5} />
    </ToolbarItem>
  );
};

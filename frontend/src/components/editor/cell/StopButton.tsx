/* Copyright 2024 Marimo. All rights reserved. */
import { SquareIcon } from "lucide-react";
import { Button } from "@/components/editor/inputs/Inputs";
import { Tooltip } from "../../ui/tooltip";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { cn } from "../../../utils/cn";
import { sendInterrupt } from "@/core/network/requests";
import { useShouldShowInterrupt } from "./useShouldShowInterrupt";
import type { RuntimeState } from "@/core/network/types";
import { Functions } from "@/utils/functions";

export const StopButton = (props: {
  status: RuntimeState;
  appClosed: boolean;
}): JSX.Element => {
  const { appClosed, status } = props;

  const running = status === "running";

  // Show the interrupt button after 200ms to avoid flickering.
  const showInterrupt = useShouldShowInterrupt(running);

  return (
    <Tooltip content={renderShortcut("global.interrupt")} usePortal={false}>
      <Button
        className={cn(
          !showInterrupt && "hover-action",
          (appClosed || !showInterrupt) &&
            "inactive-button active:shadow-xsSolid",
        )}
        onClick={showInterrupt ? sendInterrupt : Functions.NOOP}
        color={showInterrupt ? "yellow" : "disabled"}
        shape="circle"
        size="small"
        data-testid="run-button"
      >
        <SquareIcon strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};

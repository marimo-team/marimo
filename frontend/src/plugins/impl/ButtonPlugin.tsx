/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import { KeyboardHotkeys } from "@/components/shortcuts/renderShortcut";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Button } from "../../components/ui/button";
import { renderHTML } from "../core/RenderHTML";
import type { IPlugin, IPluginProps } from "../types";
import { type Intent, zodIntent } from "./common/intent";

interface Data {
  label: string;
  kind: Intent;
  disabled: boolean;
  fullWidth: boolean;
  tooltip?: string;
  keyboardShortcut?: string;
}

export class ButtonPlugin implements IPlugin<number, Data> {
  tagName = "marimo-button";

  validator = z.object({
    label: z.string(),
    kind: zodIntent,
    disabled: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    tooltip: z.string().optional(),
    keyboardShortcut: z.string().optional(),
  });

  render(props: IPluginProps<number, Data>): JSX.Element {
    const {
      data: { disabled, kind, label, fullWidth, tooltip, keyboardShortcut },
    } = props;
    // value counts number of times button was clicked
    const button = (
      <Button
        data-testid="marimo-plugin-button"
        variant={kindToButtonVariant(kind)}
        disabled={disabled}
        size="xs"
        keyboardShortcut={keyboardShortcut}
        className={cn({
          "w-full": fullWidth,
          "w-fit": !fullWidth,
        })}
        onClick={(evt) => {
          if (disabled) {
            return;
          }
          evt.stopPropagation();
          props.setValue((v) => v + 1);
        }}
        type="submit"
      >
        {renderHTML({ html: label })}
      </Button>
    );

    const tooltipContent =
      keyboardShortcut && !tooltip ? (
        <KeyboardHotkeys shortcut={keyboardShortcut} />
      ) : (
        tooltip
      );

    if (tooltipContent) {
      return (
        <TooltipProvider>
          <Tooltip content={tooltipContent} delayDuration={200}>
            {button}
          </Tooltip>
        </TooltipProvider>
      );
    }

    return button;
  }
}

function kindToButtonVariant(kind: Intent) {
  switch (kind) {
    case "neutral":
      return "secondary";
    case "danger":
      return "destructive";
    case "warn":
      return "warn";
    case "success":
      return "success";
  }
}

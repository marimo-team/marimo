/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import { Button } from "../../components/ui/button";
import { renderHTML } from "../core/RenderHTML";
import { Intent, zodIntent } from "./common/intent";
import { cn } from "@/utils/cn";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";

interface Data {
  label: string;
  kind: Intent;
  disabled: boolean;
  fullWidth: boolean;
  tooltip?: string;
}

export class ButtonPlugin implements IPlugin<number, Data> {
  tagName = "marimo-button";

  validator = z.object({
    label: z.string(),
    kind: zodIntent,
    disabled: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    tooltip: z.string().optional(),
  });

  render(props: IPluginProps<number, Data>): JSX.Element {
    const {
      data: { disabled, kind, label, fullWidth, tooltip },
    } = props;
    // value counts number of times button was clicked
    const button = (
      <Button
        data-testid="marimo-plugin-button"
        variant={kindToButtonVariant(kind)}
        disabled={disabled}
        size="xs"
        className={cn({
          "w-full": fullWidth,
        })}
        onClick={() => {
          if (disabled) {
            return;
          }
          props.setValue((v) => v + 1);
        }}
        type="submit"
      >
        {renderHTML({ html: label })}
      </Button>
    );

    if (tooltip) {
      return (
        <TooltipProvider>
          <Tooltip content={tooltip}>{button}</Tooltip>
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

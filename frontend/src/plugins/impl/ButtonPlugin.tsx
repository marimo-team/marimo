/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import { KeyboardHotkeys } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
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
    const renderedLabel = renderHTML({ html: label });
    // A disabled <button> carries `pointer-events: none` (via buttonVariants),
    // which is inherited by its whole subtree. If the label contains a
    // `data-tooltip` element (e.g.
    // `mo.ui.button(label="<div data-tooltip='...'>", disabled=True)`), that
    // element becomes a Radix Tooltip trigger nested inside the button and
    // would never receive the pointer events (onPointerMove/onPointerLeave)
    // Radix opens the tooltip on — so the tooltip explaining *why* the button
    // is disabled can never open (#2515).
    //
    // Re-enable pointer events on just the label subtree. `display: contents`
    // makes the wrapper layout-neutral (it adds no box), and re-enabling
    // pointer events on a descendant does not resurface the disabled button:
    // the native `disabled` attribute still suppresses the button's own
    // activation/click, so the control stays disabled. We only do this when
    // disabled; an enabled button is untouched (auto is already the default).
    const labelContent = disabled ? (
      <span className="contents pointer-events-auto">{renderedLabel}</span>
    ) : (
      renderedLabel
    );
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
        {labelContent}
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
        <Tooltip content={tooltipContent} delayDuration={200}>
          {button}
        </Tooltip>
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

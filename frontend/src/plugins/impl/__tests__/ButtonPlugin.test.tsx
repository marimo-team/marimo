/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { IPluginProps } from "../../types";
import { ButtonPlugin } from "../ButtonPlugin";

// Issue #2515: a tooltip authored inside a *disabled* button's label
// (e.g. `mo.ui.button(label="<div data-tooltip='...'>", disabled=True)`)
// must stay reachable by the pointer. A disabled <button> carries
// `pointer-events: none`, which is inherited by its whole subtree, so the
// nested Radix Tooltip trigger would never receive the pointer events Radix
// opens the tooltip on. The fix keeps the trigger structurally inside the
// disabled button but wraps the label subtree in a layout-neutral
// (`display: contents`) `pointer-events-auto` wrapper, which overrides the
// inherited `pointer-events: none` for that subtree — without un-disabling
// the button.
//
// jsdom does not model CSS `pointer-events` hit-testing or the native
// `disabled` event suppression, so a hover-visibility assertion here would
// pass even against the broken code (false confidence). Instead we assert the
// structural invariant that makes the real-browser behavior possible: the
// `data-tooltip` element, though still inside the disabled button, sits under
// a `pointer-events-auto` wrapper that overrides the inherited
// `pointer-events: none`, while the button itself stays disabled.
describe("ButtonPlugin", () => {
  const LABEL_WITH_TOOLTIP =
    "<div data-tooltip='Why disabled'>Disabled button</div>";

  function renderButton(data: Partial<z.input<ButtonPlugin["validator"]>>) {
    const plugin = new ButtonPlugin();
    const props: IPluginProps<number, z.infer<ButtonPlugin["validator"]>> = {
      data: plugin.validator.parse({
        label: LABEL_WITH_TOOLTIP,
        kind: "neutral",
        ...data,
      }),
      value: 0,
      setValue: vi.fn(),
      host: document.createElement("div"),
      functions: {},
    };
    const utils = render(
      <TooltipProvider>{plugin.render(props)}</TooltipProvider>,
    );
    return {
      ...utils,
      button: utils.container.querySelector("button"),
      trigger: utils.container.querySelector("[data-tooltip]"),
      reenabledWrapper: utils.container.querySelector(".pointer-events-auto"),
    };
  }

  it("disabled: overrides inherited pointer-events:none for the tooltip trigger, without un-disabling the button", () => {
    const { button, trigger, reenabledWrapper } = renderButton({
      disabled: true,
    });
    // The button stays natively disabled (the control must not become usable).
    expect(button?.disabled).toBe(true);
    // The tooltip trigger remains structurally inside that disabled button...
    expect(trigger?.getAttribute("data-tooltip")).toBe("Why disabled");
    expect(button?.contains(trigger ?? null)).toBe(true);
    // ...but under a layout-neutral wrapper whose `pointer-events-auto`
    // overrides the `pointer-events: none` inherited from the disabled button,
    // so the trigger can receive pointer events again. `display: contents`
    // keeps the wrapper boxless (no layout change).
    expect(reenabledWrapper?.classList.contains("contents")).toBe(true);
    expect(reenabledWrapper?.contains(trigger ?? null)).toBe(true);
    expect(button?.contains(reenabledWrapper ?? null)).toBe(true);
  });

  it("enabled: leaves the label untouched (no wrapper, no behavior change)", () => {
    const { button, trigger, reenabledWrapper } = renderButton({
      disabled: false,
    });
    expect(button?.disabled).toBe(false);
    // The fix is scoped to disabled buttons: enabled buttons get no wrapper,
    // and the `data-tooltip` element renders as a direct child as before.
    expect(reenabledWrapper).toBeNull();
    expect(trigger?.parentElement).toBe(button);
  });
});

/* Copyright 2024 Marimo. All rights reserved. */
import { useEventListener } from "@/hooks/useEventListener";
import { MinimalHotkeys } from "../shortcuts/renderShortcut";
import { Button, type ButtonProps } from "../ui/button";

/* Copyright 2024 Marimo. All rights reserved. */
interface UndoButtonProps extends Omit<ButtonProps, "onClick"> {
  onClick?: (event: Pick<Event, "preventDefault" | "stopPropagation">) => void;
}

export const UndoButton = (props: UndoButtonProps) => {
  // Add ctrl-z or meta-z event listener
  useEventListener(
    globalThis,
    "keydown",
    (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "z") {
        event.preventDefault();
        event.stopPropagation();
        props.onClick?.(event);
      }
    },
    {
      capture: true,
    },
  );

  const children = props.children ?? "Undo";

  return (
    <Button data-testid="undo-button" size="sm" variant="outline" {...props}>
      {children} <MinimalHotkeys className="ml-2" shortcut="cmd-z" />
    </Button>
  );
};

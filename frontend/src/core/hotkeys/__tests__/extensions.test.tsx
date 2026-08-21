/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it } from "vitest";
import {
  keyboardShortcutExtensionsAtom,
  platformAtom,
} from "@/core/config/config";
import {
  KeyboardShortcutExtensions,
  KEYBOARD_SHORTCUT_EVENT,
} from "../extensions";

it("dispatches the extension action through the registered shortcut", () => {
  const action = "extension.companion.show-message" as const;
  const store = createStore();
  store.set(platformAtom, "linux");
  store.set(keyboardShortcutExtensionsAtom, {
    [action]: {
      name: "Show companion message",
      group: "Other",
      key: "Mod-Shift-Y",
    },
  });

  let detail: unknown;
  const listener = (event: Event) => {
    if (event instanceof CustomEvent) {
      detail = event.detail;
    }
  };
  window.addEventListener(KEYBOARD_SHORTCUT_EVENT, listener);

  const result = render(
    <Provider store={store}>
      <KeyboardShortcutExtensions />
    </Provider>,
  );
  document.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "y",
      ctrlKey: true,
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    }),
  );

  expect(detail).toEqual({ action });
  result.unmount();
  window.removeEventListener(KEYBOARD_SHORTCUT_EVENT, listener);
});

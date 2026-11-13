/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import type { CompletionResultMessage } from "@/core/kernel/messages";
import { Autocompleter } from "../Autocompleter";

const docstring = [
  "<p>Docs for <code>f</code></p>",
  "<marimo-tex>||(x^2||)</marimo-tex>",
  // Other marimo plugin elements are dropped from docstrings.
  `<marimo-mime-renderer data-mime='"text/plain"' data-data='"x"'></marimo-mime-renderer>`,
].join("");

const message = {
  completion_id: "1",
  prefix_length: 0,
  options: [{ name: "f", type: "function", completion_info: docstring }],
} as CompletionResultMessage;

describe("Autocompleter", () => {
  it.each([
    [
      "completion info",
      () =>
        (
          Autocompleter.asCompletionResult(0, message).options[0]
            .info as () => HTMLElement
        )(),
    ],
    [
      "hover tooltips",
      () =>
        Autocompleter.asHoverTooltip({ position: 0, message })!.create(
          {} as EditorView,
        ).dom,
    ],
  ])("keeps only marimo-tex among plugin elements in %s", (_, render) => {
    const dom = render();
    expect(dom.querySelector("code")?.textContent).toBe("f");
    expect(dom.querySelector("marimo-tex")?.textContent).toBe("||(x^2||)");
    expect(dom.querySelector("marimo-mime-renderer")).toBeNull();
  });
});

/* Copyright 2026 Marimo. All rights reserved. */

import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { darkTheme } from "../dark";
import { lightTheme } from "../light";

const mounted: Array<{ host: HTMLDivElement; view: EditorView }> = [];

function mountTheme(extension: Extension) {
  const host = document.createElement("div");
  document.body.append(host);
  const root = host.attachShadow({ mode: "open" });
  const parent = document.createElement("div");
  root.append(parent);
  const view = new EditorView({ extensions: extension, parent, root });
  mounted.push({ host, view });

  const style = root.querySelector("style");
  if (!style) {
    throw new Error("CodeMirror did not mount its theme styles");
  }
  return { css: style.textContent ?? "", view };
}

afterEach(() => {
  for (const { host, view } of mounted.splice(0)) {
    view.destroy();
    host.remove();
  }
});

const themeCases = [
  {
    name: "light",
    extension: lightTheme,
    dark: false,
    selectionAlias: "var(--cm-selection-background-light)",
    reactiveColor: "var(--cm-reactive-reference-color-light)",
  },
  {
    name: "dark",
    extension: darkTheme,
    dark: true,
    selectionAlias: "var(--cm-selection-background-dark)",
    reactiveColor: "var(--cm-reactive-reference-color-dark)",
  },
] as const;

describe.each(themeCases)("$name theme", (theme) => {
  it("uses the production theme tokens", () => {
    const { css, view } = mountTheme(theme.extension);

    expect(view.state.facet(EditorView.darkTheme)).toBe(theme.dark);
    expect(css).toContain(
      `--cm-selection-background: ${theme.selectionAlias};`,
    );
    expect(css).toContain("background-color: var(--cm-selection-background);");
    expect(css).toContain(`color: ${theme.reactiveColor};`);
    expect(css).toContain(
      "border-bottom: 2px solid var(--cm-reactive-reference-border-color);",
    );

    const hoverRule = css
      .split("\n")
      .find((rule) => rule.includes(".mo-cm-reactive-reference-hover"));
    expect(hoverRule).toBeDefined();
    expect(hoverRule).toContain("cursor: pointer;");
    expect(hoverRule).not.toContain("border-bottom");
  });
});

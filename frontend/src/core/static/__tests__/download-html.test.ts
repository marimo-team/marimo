/* Copyright 2023 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { constructHTML } from "../download-html";
import { CellId } from "@/core/cells/ids";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import { JSDOM } from "jsdom";
// @ts-expect-error - no types
import prettier from "prettier";

const DOC = `
<html lang="en">
  <head>
    <style id="random-style">
      #thing {
        visibility: hidden;
      }
    </style>
    <meta charset="utf-8" />
    <link rel="icon" href="/favicon.ico" />
    <link rel="preload" href="/assets/gradient-6c6e9bb3.png" as="image" />
    <link rel="preload" href="/assets/noise-b5c8172e.png" as="image" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="a marimo app" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    <link rel="manifest" href="/manifest.json" />
    <script>
      function __resizeIframe(obj) {
        obj.style.height = obj.contentWindow.document.documentElement.scrollHeight + 'px';
      }
    </script>
  </head>
  <body class="light light-theme">
    <marimo-filename hidden="">app.py</marimo-filename>
    <marimo-mode data-mode="edit" hidden=""></marimo-mode>
    <marimo-version data-version="0.1.44" hidden=""></marimo-version>
    <marimo-user-config
      data-config='{"display": {"theme": "light"}, "keymap": {"preset": "default"}, "save": {"autosave": "after_delay", "format_on_save": true, "autosave_delay": 1000}, "server": {"browser": "default"}, "experimental": {"layouts": true, "theming": true}, "runtime": {"auto_instantiate": true}, "completion": {"activate_on_typing": true, "copilot": true}}'
      hidden=""
    ></marimo-user-config>
    <marimo-app-config data-config='{"width": "full", "layout_file": null}' hidden=""></marimo-app-config>

    <title>app</title>
    <script type="module" crossorigin="" src="/assets/index-2e140915.js"></script>
    <link rel="stylesheet" href="/assets/index-116d8088.css" />

    <div id="root">
      <main>App HTML should not render</main>
    </div>
  </body>
</html>
`;

describe("download-html", () => {
  it("should construct html correctly", async () => {
    const cellId = "1" as CellId;
    const version = "0.1.44";
    const result = constructHTML({
      version: version,
      notebookState: {
        cellIds: [cellId],
        cellData: {
          [cellId]: createCell({
            id: cellId,
            name: "cell",
            code: "code",
          }),
        },
        cellRuntime: { [cellId]: createCellRuntimeState() },
      },
      assetUrl: `https://cdn.jsdelivr.net/npm/@marimo-team/frontend@${version}/dist`,
      filename: "app",
      existingDocument: new JSDOM(DOC).window.document,
    });

    const formattedResult = prettier.format(result, {
      parser: "html",
    });
    expect(formattedResult).toMatchSnapshot();
  });
});

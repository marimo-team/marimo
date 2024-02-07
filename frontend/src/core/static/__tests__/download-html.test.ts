/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { constructHTML, visibleForTesting } from "../download-html";
import { CellId } from "@/core/cells/ids";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import { JSDOM } from "jsdom";
import prettier from "prettier";
import { Base64String } from "@/utils/json/base64";

const { updateAssetUrl } = visibleForTesting;

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
    <link
      rel="preload"
      href="/assets/Lora-VariableFont_wght-dqKLWsPt.ttf"
      as="font"
      crossorigin="anonymous"
    />
    <link
      rel="preload"
      href="/assets/PTSans-Regular-sS9EvFu5.ttf"
      as="font"
      crossorigin="anonymous"
    />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="a marimo app" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    <link rel="manifest" href="/manifest.json" />
    <script data-marimo="true">
      function __resizeIframe(obj) {
        // Resize the iframe to the height of the content
        obj.style.height =
          obj.contentWindow.document.documentElement.scrollHeight + "px";

        // Resize the iframe when the content changes
        const resizeObserver = new ResizeObserver((entries) => {
          obj.style.height =
            obj.contentWindow.document.documentElement.scrollHeight + "px";
        });
        resizeObserver.observe(obj.contentWindow.document.body);
      }
    </script>
  </head>
  <body class="light light-theme">
    <marimo-filename hidden="">app.py</marimo-filename>
    <marimo-mode data-mode="edit" hidden=""></marimo-mode>
    <marimo-version data-version="0.1.44" hidden=""></marimo-version>
    <marimo-server-token data-token="123" hidden=""></marimo-server-token>
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
            config: {
              hide_code: true,
            },
          }),
        },
        cellRuntime: { [cellId]: createCellRuntimeState() },
      },
      files: {
        "/@file/note.txt": {
          base64: "data:text/plain;base64,bm90ZQo=" as Base64String,
        },
      },
      code: "import marimo as mo\n\nmo.html('<h1>hello</h1>')",
      assetUrl: `https://cdn.jsdelivr.net/npm/@marimo-team/frontend@${version}/dist`,
      existingDocument: new JSDOM(DOC).window.document,
    });

    const formattedResult = await prettier.format(result, {
      parser: "html",
    });
    expect(formattedResult).toMatchSnapshot();
  });
});

describe("updateAssetUrl", () => {
  const assetBaseUrl =
    "https://cdn.jsdelivr.net/npm/@marimo-team/frontend@0.1.43/dist";

  it('should convert relative URL starting with "./"', () => {
    const existingUrl = "./assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it('should convert relative URL starting with "/"', () => {
    const existingUrl = "/assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it("should convert absolute URL from a different origin", () => {
    const existingUrl = "https://localhost:8080/assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it("should not modify URL from the same origin", () => {
    // Assuming window.location.origin is 'https://localhost:8080'
    const existingUrl = "https://localhost:8080/assets/index-c78b8d10.js";
    // Mock window.location.origin to match the existingUrl's origin
    Object.defineProperty(window, "location", {
      value: {
        origin: "https://localhost:8080",
      },
    });

    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(existingUrl);
  });
});

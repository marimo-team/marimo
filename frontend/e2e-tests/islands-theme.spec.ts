/* Copyright 2026 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { build } from "vite";

let css: string;

test.beforeAll(async () => {
  const previous = process.env.VITE_MARIMO_ISLANDS;
  process.env.VITE_MARIMO_ISLANDS = "true";
  try {
    const bundles = await build({
      configFile: false,
      root: fileURLToPath(new URL("..", import.meta.url)),
      logLevel: "silent",
      build: {
        write: false,
        cssCodeSplit: true,
        lib: {
          entry: fileURLToPath(
            new URL("./fixtures/islands-theme.css", import.meta.url),
          ),
          formats: ["es"],
        },
      },
    });
    css = (Array.isArray(bundles) ? bundles : [bundles])
      .flatMap((bundle) => ("output" in bundle ? bundle.output : []))
      .flatMap((output) =>
        output.type === "asset" && output.fileName.endsWith(".css")
          ? [String(output.source)]
          : [],
      )
      .join("\n");
    expect(css).not.toBe("");
  } finally {
    if (previous === undefined) {
      delete process.env.VITE_MARIMO_ISLANDS;
    } else {
      process.env.VITE_MARIMO_ISLANDS = previous;
    }
  }
});

for (const host of ["html", "body", "shadow"] as const) {
  test(`resolved-light namespaces override a dark ${host} host`, async ({
    page,
  }) => {
    await page.setContent(`<!doctype html><html><body>
      <div id="mount" class="marimo"></div>
    </body></html>`);
    await page.addStyleTag({ content: css });
    await page.evaluate(
      ({ css, host }) => {
        const mount = document.querySelector("#mount")!;
        const target =
          host === "shadow" ? mount.attachShadow({ mode: "open" }) : mount;
        if (target instanceof ShadowRoot) {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(css);
          target.adoptedStyleSheets = [sheet];
        }
        target.innerHTML = `<div class="marimo light block dark:hidden" id="namespace">
        <div class="block dark:hidden" id="probe" style="color:var(--foreground);background:var(--slate-2);border:1px solid var(--destructive)">Output</div>
      </div>`;
      },
      { css, host },
    );

    const namespace = page.locator("#namespace");
    const probe = page.locator("#probe");
    const readColors = () =>
      probe.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          scheme: style.colorScheme,
          color: style.color,
          background: style.backgroundColor,
          border: style.borderTopColor,
        };
      });
    const lightColors = await readColors();
    expect(lightColors.scheme).toBe("light");
    await page.evaluate((host) => {
      document
        .querySelector(host === "shadow" ? "body" : host)!
        .classList.add("dark");
    }, host);
    expect(await readColors()).toEqual(lightColors);
    await expect(namespace).toHaveCSS("display", "block");
    await expect(probe).toHaveCSS("display", "block");

    await namespace.evaluate((element) =>
      element.classList.replace("light", "dark"),
    );
    const darkColors = await readColors();
    expect(darkColors.scheme).toBe("dark");
    for (const property of ["color", "background", "border"] as const) {
      expect(darkColors[property]).not.toBe(lightColors[property]);
    }
    await expect(probe).toHaveCSS("display", "none");
    await namespace.evaluate((element) =>
      element.classList.replace("dark", "light"),
    );
    expect(await readColors()).toEqual(lightColors);
    await expect(namespace).toHaveCSS("display", "block");
    await expect(probe).toHaveCSS("display", "block");

    if (host !== "shadow") {
      await namespace.evaluate((element) => element.classList.remove("light"));
      expect(await readColors()).toEqual(darkColors);
      await expect(probe).toHaveCSS("display", "none");
    }
  });
}

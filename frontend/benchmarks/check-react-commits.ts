/* Copyright 2026 Marimo. All rights reserved. */

import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { chromium } from "@playwright/test";
import { build } from "vite";
import { installReactCommitRecorder } from "./react-commits.ts";

declare global {
  interface Window {
    incrementEdited?: () => void;
    incrementParent?: () => void;
  }
}

const require = createRequire(import.meta.url);
const result = await build({
  configFile: false,
  logLevel: "error",
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  resolve: {
    alias: [
      { find: /^react$/, replacement: require.resolve("react") },
      {
        find: /^react-dom\/client$/,
        replacement: require.resolve("react-dom/profiling"),
      },
    ],
  },
  plugins: [
    {
      name: "react-commit-probe",
      resolveId(id) {
        if (id.endsWith("/react-commit-probe")) {
          return "\0react-commit-probe";
        }
      },
      load(id) {
        if (id !== "\0react-commit-probe") {
          return;
        }
        return `
          import { createElement as h, memo, useState } from "react";
          import { createRoot } from "react-dom/client";
          const Stable = memo(function Stable() {
            return h("span", null, "stable");
          });
          const Edited = memo(function Edited() {
            const [value, setValue] = useState(0);
            window.incrementEdited = () => setValue((n) => n + 1);
            return h("span", null, value);
          });
          function App() {
            const [value, setValue] = useState(0);
            window.incrementParent = () => setValue((n) => n + 1);
            return h("div", { "data-count": value }, h(Edited), h(Stable));
          }
          createRoot(document.body).render(h(App));
        `;
      },
    },
  ],
  build: {
    write: false,
    minify: false,
    lib: { entry: "react-commit-probe", formats: ["iife"], name: "Probe" },
  },
});
const output = Array.isArray(result) ? result[0] : result;
assert("output" in output);
const chunk = output.output.find((entry) => entry.type === "chunk");
assert(chunk);

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await installReactCommitRecorder(page);
  await page.route("http://react-commit-probe.test/", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<html><body></body></html>",
    }),
  );
  await page.goto("http://react-commit-probe.test/");
  await page.addScriptTag({ content: chunk.code });
  await page.waitForFunction(() => window.incrementEdited);
  await page.evaluate(() => {
    window.editingMetrics = {
      phase: "probe",
      samples: [],
      events: [],
      longTasks: [],
    };
    window.editingCommits?.reset();
  });
  for (let i = 1; i <= 5; i++) {
    await page.evaluate((iteration) => {
      if (iteration <= 3) {
        window.incrementEdited?.();
      } else {
        window.incrementParent?.();
      }
    }, i);
    await page.waitForFunction(
      (expected) => window.editingCommits?.commits.length === expected,
      i,
    );
  }
  const commits = await page.evaluate(() => window.editingCommits?.commits);
  assert(commits);
  assert(commits.every((commit) => Number.isFinite(commit.renderDuration)));
  const counts: Record<string, number> = {};
  for (const commit of commits) {
    for (const component of commit.components) {
      counts[component.name] = (counts[component.name] ?? 0) + 1;
    }
  }
  assert.deepEqual(counts, { Edited: 3, App: 2 });
  process.stdout.write(
    "React recorder: 3 child renders, 2 parent renders, 0 memoized sibling renders.\n",
  );
} finally {
  await browser.close();
}

/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, describe, expect, it } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { codeAtom, filenameAtom } from "@/core/saving/file-state";
import { getStaticNotebookRunTarget, StaticBanner } from "../static-banner";

function renderBanner(sharing?: {
  html?: boolean;
  wasm?: boolean;
  molab?: boolean;
}) {
  const store = createStore();
  store.set(codeAtom, "import marimo\n");
  store.set(filenameAtom, "/notebooks/my notebook.py");
  store.set(userConfigAtom, {
    ...defaultUserConfig(),
    sharing,
  });
  window.__MARIMO_STATIC__ = { files: {} };

  return render(
    <Provider store={store}>
      <StaticBanner />
    </Provider>,
  );
}

async function openDialog() {
  fireEvent.click(screen.getByTestId("static-notebook-dialog-trigger"));
  return screen.findByRole("dialog");
}

describe("StaticBanner", () => {
  afterEach(() => {
    delete window.__MARIMO_STATIC__;
  });

  it("shows the molab option by default", async () => {
    renderBanner();
    await openDialog();

    expect(screen.getByRole("link", { name: "Open in molab" })).toHaveAttribute(
      "href",
      expect.stringContaining("molab.marimo.io/new"),
    );
  });

  it("hides the molab option when sharing is disabled", async () => {
    renderBanner({ html: false, wasm: false, molab: false });
    await openDialog();

    expect(
      screen.queryByRole("link", { name: "Open in molab" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/cloud-hosted notebook platform/),
    ).not.toBeInTheDocument();
  });

  it("offers uv, pip, and conda commands", async () => {
    renderBanner({ molab: false });
    await openDialog();

    expect(screen.getByRole("tab", { name: "uv" })).toBeVisible();
    expect(
      screen.getByText("uvx marimo edit --sandbox 'my notebook.py'"),
    ).toBeVisible();

    fireEvent.mouseDown(screen.getByRole("tab", { name: "pip" }), {
      button: 0,
    });
    expect(screen.getByText(/pip install marimo/)).toBeVisible();

    fireEvent.mouseDown(screen.getByRole("tab", { name: "conda" }), {
      button: 0,
    });
    expect(
      screen.getByText(/conda install -c conda-forge marimo/),
    ).toBeVisible();
  });
});

describe("getStaticNotebookRunTarget", () => {
  it.each([
    ["file:///tmp/notebook.html", "notebook.py"],
    ["http://localhost:8000/report", "notebook.py"],
    ["https://example.com/report", "notebook.py"],
  ])("falls back to the downloaded filename for %s", (href, expected) => {
    expect(getStaticNotebookRunTarget(href, "notebook.py")).toBe(expected);
  });

  it.each([
    [
      "https://example.com/notebook.html#section",
      "https://example.com/notebook.html",
    ],
    [
      "https://static.marimo.app/static/example",
      "https://static.marimo.app/static/example",
    ],
    [
      "https://molab.marimo.io/notebooks/nb_example/app",
      "https://molab.marimo.io/notebooks/nb_example/app",
    ],
  ])("uses URLs supported by marimo edit: %s", (href, expected) => {
    expect(getStaticNotebookRunTarget(href, "notebook.py")).toBe(expected);
  });
});

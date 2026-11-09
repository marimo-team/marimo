/* Copyright 2026 Marimo. All rights reserved. */

import { act } from "react";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { cellId } from "@/__tests__/branded";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { notebookAtom } from "@/core/cells/cells";
import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
  ISLANDS_JSON_SCRIPT_TYPE,
} from "@/core/islands/constants";
import { islandsPendingInitialRunsAtom } from "@/core/islands/state";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { buildIslandHTML } from "../../__tests__/test-utils";
import { parseMarimoIslandApps } from "../../parse";
import { MarimoIslandElement } from "../web-components";

beforeAll(() => {
  setReactActEnvironment(true);
  if (!customElements.get(ISLAND_TAG_NAMES.ISLAND)) {
    customElements.define(ISLAND_TAG_NAMES.ISLAND, MarimoIslandElement);
  }
});

afterAll(() => {
  setReactActEnvironment(false);
});

beforeEach(() => {
  store.set(notebookAtom, MockNotebook.notebookState({ cellData: {} }));
  store.set(islandsPendingInitialRunsAtom, new Set());
  store.set(requestClientAtom, MockRequestClient.create());
});

afterEach(async () => {
  await actAndFlush(() => document.body.replaceChildren());
  store.set(requestClientAtom, null);
  document.body.removeAttribute("style");
  vi.unstubAllEnvs();
});

describe("MarimoIslandElement lifecycle", () => {
  it.each([true, false])(
    "synchronizes the theme of a reactive=%s island across reconnects",
    async (reactive) => {
      vi.stubEnv("VITE_MARIMO_ISLANDS", "true");
      if (reactive) {
        setNotebook("runtime-cell", "runtime output");
      }
      const { container, island } = createThemeIsland(reactive);
      document.body.style.colorScheme = "dark";
      await actAndFlush(() => document.body.append(container));
      expect(island).toHaveClass("marimo", "dark");
      await actAndFlush(() => {
        document.body.style.colorScheme = "light";
      });
      expect(island).toHaveClass("marimo", "light");
      expect(island).not.toHaveClass("dark");
      await actAndFlush(() => island.remove());
      await actAndFlush(() => {
        document.body.style.colorScheme = "dark";
      });
      expect(island).toHaveClass("light");
      await actAndFlush(() => container.append(island));
      expect(island).toHaveClass("dark");
    },
  );

  it("can disconnect before its scheduled render and reconnect with the current theme", async () => {
    vi.stubEnv("VITE_MARIMO_ISLANDS", "true");
    const { container, island } = createThemeIsland(false);
    document.body.style.colorScheme = "dark";
    await actAndFlush(() => {
      document.body.append(container);
      island.remove();
    });
    expect(island.querySelector("marimo-cell-output")).not.toBeNull();
    await actAndFlush(() => {
      document.body.style.colorScheme = "light";
    });
    expect(island).toHaveClass("dark");
    await actAndFlush(() => container.append(island));
    expect(island).toHaveClass("light");
    expect(island.textContent).toContain("static output");
  });

  it("keeps static output until the initial run completes", async () => {
    store.set(islandsPendingInitialRunsAtom, new Set([1]));
    setNotebook("runtime-cell", "runtime output");
    const container = document.createElement("div");
    container.innerHTML = `
      <marimo-island
        data-app-id="app-1"
        data-cell-id="runtime-cell"
        data-cell-idx="0"
        data-reactive="true"
      >
        <marimo-cell-output><div>static output</div></marimo-cell-output>
        <marimo-cell-code hidden>${encodeURIComponent("value = 1")}</marimo-cell-code>
      </marimo-island>
    `;

    await actAndFlush(() => document.body.append(container));

    const island = container.querySelector<HTMLElement>(
      ISLAND_TAG_NAMES.ISLAND,
    );
    expect(island?.textContent).toContain("static output");
    expect(island?.textContent).not.toContain("runtime output");

    await actAndFlush(() => {
      store.set(islandsPendingInitialRunsAtom, new Set());
    });

    expect(island?.textContent).toContain("runtime output");
    expect(island?.textContent).not.toContain("static output");
  });

  it("binds a reactive island after its runtime cell index is materialized", async () => {
    setNotebook("outgoing-cell", "outgoing runtime output");
    const container = document.createElement("div");
    container.innerHTML = `
      <marimo-island data-app-id="app-1" data-reactive="true">
        <marimo-cell-output><div>initial output</div></marimo-cell-output>
        <marimo-cell-code hidden>${encodeURIComponent("value = 1")}</marimo-cell-code>
      </marimo-island>
    `;
    await actAndFlush(() => document.body.append(container));

    const island = container.querySelector<HTMLElement>(
      ISLAND_TAG_NAMES.ISLAND,
    );
    expect(island).not.toBeNull();
    expect(island?.getAttribute("data-status")).toBeNull();

    await actAndFlush(() => {
      parseMarimoIslandApps(container);
    });

    expect(island?.textContent).toContain("outgoing runtime output");

    await actAndFlush(() => {
      setNotebook("runtime-cell");
    });

    expect(island?.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(island?.getAttribute("data-status")).toBe("idle");

    await actAndFlush(() => {
      island?.remove();
      if (island) {
        container.append(island);
      }
    });
    expect(island?.textContent).toContain("initial output");

    island?.setAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID, "source-cell");
    island?.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "false");
    expect((island as MarimoIslandElement | null)?.cellId).toBeUndefined();
  });

  it("refreshes a reused payload island and clears an old app binding", async () => {
    const container = document.createElement("div");
    container.innerHTML = `
      <marimo-island
        data-app-id="app-1"
        data-cell-id="cell-1"
        data-reactive="true"
      >
        <marimo-cell-output><div>old output</div></marimo-cell-output>
        <marimo-cell-code hidden>${encodeURIComponent('print("old")')}</marimo-cell-code>
      </marimo-island>
    `;
    const script = document.createElement("script");
    script.type = ISLANDS_JSON_SCRIPT_TYPE;
    script.textContent = payloadSource({
      code: 'print("unchanged")',
      outputHtml: "<div>old output</div>",
    });
    container.append(script);
    await actAndFlush(() => document.body.append(container));

    await actAndFlush(() => {
      parseMarimoIslandApps(container);
      script.textContent = payloadSource({
        code: 'print("unchanged")',
        outputHtml: "<div>updated output</div>",
      });
      parseMarimoIslandApps(container);
    });

    const island = container.querySelector<HTMLElement>(
      ISLAND_TAG_NAMES.ISLAND,
    );
    expect(island?.textContent).toContain("updated output");
    expect(island?.textContent).not.toContain("old output");
    expect(island?.querySelector(ISLAND_TAG_NAMES.CELL_OUTPUT)).toBeNull();

    await actAndFlush(() => {
      setNotebook("outgoing-cell", "outgoing runtime output");
    });
    expect(island?.textContent).toContain("outgoing runtime output");

    await actAndFlush(() => {
      island?.setAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID, "app-2");
      island?.setAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID, "cell-2");
      script.textContent = payloadSource({
        appId: "app-2",
        cellId: "cell-2",
        code: 'print("next")',
        outputHtml: "<div>next app output</div>",
      });
      parseMarimoIslandApps(container);
    });

    expect(island?.textContent).toContain("next app output");
    expect(island?.textContent).not.toContain("outgoing runtime output");
  });
});

function createThemeIsland(reactive: boolean) {
  const container = document.createElement("div");
  container.innerHTML = buildIslandHTML([
    {
      appId: "app-1",
      cellId: "runtime-cell",
      reactive,
      code: "x = 1",
      output: "<pre>static output</pre>",
    },
  ]);
  const island = container.querySelector<HTMLElement>(ISLAND_TAG_NAMES.ISLAND)!;
  return { container, island };
}

function setNotebook(id: string, output?: string): void {
  const runtimeCellId = cellId(id);
  store.set(
    notebookAtom,
    MockNotebook.notebookState({ cellData: { [runtimeCellId]: {} } }),
  );
  MockExecutions.seed(
    store,
    output === undefined
      ? []
      : [
          MockExecutions.shown(runtimeCellId, {
            mimetype: "text/html",
            data: `<div>${output}</div>`,
          }),
        ],
  );
}

function payloadSource({
  appId = "app-1",
  cellId = "cell-1",
  code,
  outputHtml,
}: {
  appId?: string;
  cellId?: string;
  code: string;
  outputHtml: string;
}): string {
  return JSON.stringify({
    schemaVersion: 1,
    appId,
    cells: [
      {
        cellId,
        code,
        outputHtml,
        outputMimetype: "text/html",
        reactive: true,
        displayCode: false,
        displayOutput: true,
      },
    ],
  });
}

async function actAndFlush(action: () => void): Promise<void> {
  await act(async () => {
    action();
    await Promise.resolve();
  });
}

function setReactActEnvironment(value: boolean): void {
  (
    globalThis as typeof globalThis & {
      IS_REACT_ACT_ENVIRONMENT: boolean;
    }
  ).IS_REACT_ACT_ENVIRONMENT = value;
}

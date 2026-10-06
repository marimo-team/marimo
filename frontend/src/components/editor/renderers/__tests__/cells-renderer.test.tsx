/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import { parseAppConfig } from "@/core/config/config-schema";
import { initialLayoutState, layoutStateAtom } from "@/core/layout/state";
import { type AppMode, captureModeAtom, kioskModeAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import { CellsRenderer } from "../cells-renderer";
import type { LayoutType } from "../types";

function renderWithStore(
  mode: AppMode,
  {
    kiosk = false,
    capture = false,
    layout = "vertical",
    withEmptyCell = false,
  }: {
    kiosk?: boolean;
    capture?: boolean;
    layout?: LayoutType;
    withEmptyCell?: boolean;
  } = {},
) {
  const store = createStore();
  store.set(requestClientAtom, MockRequestClient.create());
  store.set(kioskModeAtom, kiosk);
  store.set(captureModeAtom, capture);
  if (withEmptyCell) {
    const id = cellId("cell-a");
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [id]: {} },
        cellRuntime: {
          [id]: {
            output: { channel: "output", mimetype: "text/plain", data: "" },
          },
        },
      }),
    );
  }
  store.set(layoutStateAtom, {
    ...initialLayoutState(),
    selectedLayout: layout,
  });

  return render(
    <Provider store={store}>
      <CellsRenderer appConfig={parseAppConfig({})} mode={mode}>
        <div data-testid="notebook-children" />
      </CellsRenderer>
    </Provider>,
  );
}

describe("CellsRenderer", () => {
  it("keeps empty-output metadata when the grid omits the cell", () => {
    const { container } = renderWithStore("edit", {
      kiosk: true,
      capture: true,
      layout: "grid",
      withEmptyCell: true,
    });
    expect(container.querySelector("#output-cell-a")).toBeNull();
    expect(
      container
        .querySelector('[data-cell-output-id="cell-a"]')
        ?.getAttribute("data-output-state"),
    ).toBe("empty");
  });

  it.each([
    { kiosk: false, capture: false },
    { kiosk: false, capture: true },
    { kiosk: true, capture: false },
  ])("omits capture metadata for %j", (modes) => {
    const { container } = renderWithStore("edit", {
      ...modes,
      layout: "grid",
      withEmptyCell: true,
    });
    expect(container.querySelector("[data-cell-output-id]")).toBeNull();
  });
  it("renders children in edit mode", () => {
    const { queryByTestId } = renderWithStore("edit");
    expect(queryByTestId("notebook-children")).toBeTruthy();
  });

  it("keeps children mounted in present mode with the vertical layout", () => {
    // This preserves cell output DOM across the edit <-> present toggle;
    // swapping to the layout renderer would remount every output.
    const { queryByTestId } = renderWithStore("present");
    expect(queryByTestId("notebook-children")).toBeTruthy();
  });

  it("uses the layout renderer in present mode with a non-vertical layout", () => {
    // Only present+vertical keeps the editable tree mounted; grid/slides swap
    // to their layout renderer (which remounts outputs) per the toggle logic.
    const { queryByTestId } = renderWithStore("present", { layout: "grid" });
    expect(queryByTestId("notebook-children")).toBeFalsy();
  });

  it("uses the layout renderer in read mode", () => {
    const { queryByTestId } = renderWithStore("read");
    expect(queryByTestId("notebook-children")).toBeFalsy();
  });

  it("uses the layout renderer in kiosk mode", () => {
    const { queryByTestId } = renderWithStore("edit", { kiosk: true });
    expect(queryByTestId("notebook-children")).toBeFalsy();
  });
});

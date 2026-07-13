/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { parseAppConfig } from "@/core/config/config-schema";
import { initialLayoutState, layoutStateAtom } from "@/core/layout/layout";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { CellsRenderer } from "../cells-renderer";

function renderWithStore(
  mode: AppMode,
  { kiosk = false, layout = "vertical" as const } = {},
) {
  const store = createStore();
  store.set(requestClientAtom, MockRequestClient.create());
  store.set(kioskModeAtom, kiosk);
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

  it("uses the layout renderer in read mode", () => {
    const { queryByTestId } = renderWithStore("read");
    expect(queryByTestId("notebook-children")).toBeFalsy();
  });

  it("uses the layout renderer in kiosk mode", () => {
    const { queryByTestId } = renderWithStore("edit", { kiosk: true });
    expect(queryByTestId("notebook-children")).toBeFalsy();
  });
});

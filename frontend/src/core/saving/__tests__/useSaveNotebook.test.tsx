/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { initialLayoutState, layoutStateAtom } from "@/core/layout/state";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { document } from "@/core/notebook/document/__tests__/fixtures";
import { ConnectionState } from "@/core/session/types";
import { store } from "@/core/state/jotai";
import { useNotebookDocumentSave } from "../document";
import { useSaveNotebook } from "../save-component";
import { needsSaveAtom, savedLayoutAtom } from "../state";

vi.mock("../document", () => ({ useNotebookDocumentSave: vi.fn() }));

function setup() {
  const replica = MockExecutions.seed(store, [], null, document());
  const save = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
  vi.mocked(useNotebookDocumentSave).mockReturnValue(save);
  store.set(replica.notebookAtom, {
    ...MockExecutions.notebook(),
    operations: ["notebook.edit", "notebook.save"],
  });
  store.set(
    notebookAtom,
    MockNotebook.notebookState({ cellData: { [CellId.create()]: {} } }),
  );
  store.set(connectionAtom, { state: ConnectionState.OPEN });
  const requests = MockRequestClient.create();
  store.set(requestClientAtom, requests);
  store.set(layoutStateAtom, initialLayoutState());
  store.set(savedLayoutAtom, undefined);
  const wrapper = ({ children }: PropsWithChildren) => (
    <Provider store={store}>{children}</Provider>
  );
  const { result } = renderHook(useSaveNotebook, { wrapper });
  return {
    saveNotebook: result.current.saveNotebook,
    save,
    saveLayout: requests.saveLayout,
  };
}

it("saves cells without a layout endpoint for the default layout", async () => {
  const { saveNotebook, save, saveLayout } = setup();
  await saveNotebook(false);
  expect(save).toHaveBeenCalled();
  expect(saveLayout).not.toHaveBeenCalled();
});

it("saves cells after a layout failure and retries clearing the sidecar", async () => {
  const { saveNotebook, save, saveLayout } = setup();
  store.set(savedLayoutAtom, { selectedLayout: "grid", layoutData: {} });
  saveLayout.mockRejectedValueOnce(new Error("layout unavailable"));
  await saveNotebook(false);
  expect(save).toHaveBeenCalled();
  expect(store.get(needsSaveAtom)).toBe(true);
  await saveNotebook(false);
  expect(saveLayout).toHaveBeenNthCalledWith(2, { layout: null });
  expect(store.get(needsSaveAtom)).toBe(false);
});

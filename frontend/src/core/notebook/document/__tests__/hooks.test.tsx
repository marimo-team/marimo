/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, renderHook } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import type { Document } from "../../replica/resources/document";
import {
  useNotebookCellCode,
  useNotebookCellConfig,
  useNotebookCellName,
  useNotebookCellOrder,
  useNotebookDocumentEdit,
  useNotebookDocumentSync,
} from "@/core/notebook";
import { createDocumentModel, DocumentProvider } from "..";
import { cell, CONFIG, document, withCells } from "./fixtures";
import { type FakeEdit, fakeBackend } from "../../replica/__tests__/fixtures";

const lifetimes: AbortController[] = [];

afterEach(() => {
  act(() => lifetimes.splice(0).forEach((controller) => controller.abort()));
});

function setup(
  initial: Document | null = document(),
  edit: FakeEdit = () => new Promise(() => {}),
) {
  const store = createStore();
  const source = atom(initial);
  const detached = vi.fn();
  source.onMount = () => detached;
  const controller = new AbortController();
  lifetimes.push(controller);
  const model = createDocumentModel({
    store,
    documentAtom: source,
    backendAtom: atom(fakeBackend({ edit })),
    signal: controller.signal,
  });
  const wrapper = ({ children }: PropsWithChildren) => (
    <Provider store={store}>
      <DocumentProvider model={model}>{children}</DocumentProvider>
    </Provider>
  );
  return { store, source, model, controller, detached, wrapper };
}

describe("document hooks", () => {
  it("flushes edits through the model and aborts work when the session ends", async () => {
    const accepted = withCells(document(), { c1: cell("c1", "local") });
    const edit = vi
      .fn<FakeEdit>()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: { document: accepted.revision, cells: {} },
      })
      .mockImplementation(
        () => new Deferred<Awaited<ReturnType<FakeEdit>>>().promise,
      );
    const { store, source, wrapper, controller } = setup(document(), edit);
    const { result, unmount } = renderHook(
      () => ({
        code: useNotebookCellCode("c1"),
        edit: useNotebookDocumentEdit(),
        sync: useNotebookDocumentSync(),
      }),
      { wrapper, reactStrictMode: true },
    );
    act(() => result.current.edit((tx) => tx.setCode("c1", "local")));
    expect(result.current.sync.status).toEqual({ status: "pending" });
    const { flush, retry } = result.current.sync;
    await act(async () => {
      const flushed = flush();
      // Allow the response to arrive before publishing its confirmation.
      await Promise.resolve();
      store.set(source, accepted);
      await expect(flushed).resolves.toEqual(accepted.revision);
    });
    expect(result.current.sync).toEqual({
      status: { status: "idle" },
      flush,
      retry,
    });
    expect(result.current.code).toBe("local");
    act(() => result.current.edit((tx) => tx.setCode("c1", "next")));
    await act(async () => {
      const rejected = (async () => {
        await expect(flush()).rejects.toThrow("session ended");
      })();
      await Promise.resolve();
      unmount();
      controller.abort(new Error("session ended"));
      await rejected;
    });
    expect(edit).toHaveBeenCalledTimes(2);
    expect(edit.mock.calls[1][2]?.signal?.aborted).toBe(true);
  });

  it("publishes compound edits atomically without changing host records", () => {
    const initial = document();
    const { store, source, wrapper } = setup(initial);
    const seen = vi.fn();
    const { result } = renderHook(
      () => {
        const value = {
          code: useNotebookCellCode("c1"),
          name: useNotebookCellName("c1"),
          config: useNotebookCellConfig("c1"),
          order: useNotebookCellOrder(),
        };
        seen(value);
        return { ...value, edit: useNotebookDocumentEdit() };
      },
      { wrapper },
    );
    const edit = result.current.edit;
    seen.mockClear();

    act(() =>
      edit((tx) => {
        tx.setCode("c1", "edited");
        tx.setName("c1", "renamed");
        tx.updateConfig("c1", { hide_code: true });
        tx.setOrder(["c2", "c1"]);
      }),
    );

    const expected = {
      code: "edited",
      name: "renamed",
      config: { ...CONFIG, hide_code: true },
      order: ["c2", "c1"],
    };
    expect(result.current).toEqual({ ...expected, edit });
    expect(seen.mock.calls.length).toBeGreaterThan(0);
    for (const [value] of seen.mock.calls) {
      expect(value).toEqual(expected);
    }
    expect(store.get(source)).toBe(initial);

    expect(() =>
      act(() =>
        edit((tx) => {
          tx.setCode("c1", "rolled back");
          tx.deleteCell("missing");
        }),
      ),
    ).toThrow("does not exist");
    expect(result.current).toEqual({ ...expected, edit });
  });

  it("subscribes to individual fields and keeps the edit function stable", () => {
    const { store, source, wrapper } = setup();
    const onCode = vi.fn();
    const onName = vi.fn();
    const onConfig = vi.fn();
    const onOrder = vi.fn();
    const onEdit = vi.fn();
    function Code() {
      onCode(useNotebookCellCode("c1"));
      return null;
    }
    function Name() {
      onName(useNotebookCellName("c1"));
      return null;
    }
    function Config() {
      onConfig(useNotebookCellConfig("c1"));
      return null;
    }
    function Order() {
      onOrder(useNotebookCellOrder());
      return null;
    }
    function Edit() {
      onEdit(useNotebookDocumentEdit());
      return null;
    }
    render(
      <>
        <Code />
        <Name />
        <Config />
        <Order />
        <Edit />
      </>,
      { wrapper },
    );
    const edit: ReturnType<typeof useNotebookDocumentEdit> =
      onEdit.mock.calls[0][0];
    const clear = () =>
      [onCode, onName, onConfig, onOrder, onEdit].forEach((fn) =>
        fn.mockClear(),
      );
    clear();

    act(() => edit((tx) => tx.setCode("c1", "local")));
    expect(onCode).toHaveBeenCalledWith("local");
    expect(onName).not.toHaveBeenCalled();
    expect(onConfig).not.toHaveBeenCalled();
    expect(onOrder).not.toHaveBeenCalled();
    expect(onEdit).not.toHaveBeenCalled();
    clear();

    act(() => edit((tx) => tx.setCode("c2", "other")));
    expect(
      [onCode, onName, onConfig, onOrder, onEdit].map((fn) => fn.mock.calls),
    ).toEqual([[], [], [], [], []]);

    act(() =>
      store.set(
        source,
        withCells(document(), {
          c1: cell("c1", "remote", {
            name: "host name",
            config: { ...CONFIG },
          }),
        }),
      ),
    );
    expect(onName).toHaveBeenCalledWith("host name");
    expect(onCode).not.toHaveBeenCalled();
    expect(onConfig).not.toHaveBeenCalled();
    expect(onOrder).not.toHaveBeenCalled();
    expect(onEdit).not.toHaveBeenCalled();
    clear();

    act(() =>
      edit((tx) => {
        tx.updateConfig("c1", { disabled: true });
        tx.setOrder(["c2", "c1"]);
      }),
    );
    expect(onConfig).toHaveBeenCalledWith({ ...CONFIG, disabled: true });
    expect(onOrder).toHaveBeenCalledWith(["c2", "c1"]);
    expect(onCode).not.toHaveBeenCalled();
    expect(onName).not.toHaveBeenCalled();
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("switches field subscriptions when the cell id changes", () => {
    const { wrapper } = setup();
    const { result, rerender } = renderHook(
      (id) => ({
        code: useNotebookCellCode(id),
        edit: useNotebookDocumentEdit(),
      }),
      { wrapper, initialProps: "c1" },
    );
    const edit = result.current.edit;
    rerender("c2");
    expect(result.current).toEqual({ code: "y = 2", edit });
    act(() => edit((tx) => tx.setCode("c1", "old subscription")));
    expect(result.current).toEqual({ code: "y = 2", edit });
    act(() => edit((tx) => tx.setCode("c2", "new subscription")));
    expect(result.current).toEqual({ code: "new subscription", edit });
  });

  it("distinguishes unavailable documents, hidden source, empty code, and deleted cells", () => {
    const { store, source, wrapper } = setup(null);
    const { result } = renderHook(
      () => ({
        order: useNotebookCellOrder(),
        code: useNotebookCellCode("c1"),
        name: useNotebookCellName("c1"),
        config: useNotebookCellConfig("c1"),
        edit: useNotebookDocumentEdit(),
      }),
      { wrapper },
    );
    const edit = result.current.edit;
    const absent = {
      code: undefined,
      name: undefined,
      config: undefined,
      edit,
    };
    expect(result.current).toEqual({ ...absent, order: null });
    const hidden = withCells(document(), {
      c1: cell("c1", "", { code: null }),
    });
    act(() => store.set(source, hidden));
    expect(result.current).toEqual({
      code: null,
      name: "_",
      config: CONFIG,
      order: ["c1", "c2"],
      edit,
    });
    act(() => edit((tx) => tx.setCode("c1", "")));
    expect(result.current.code).toBe("");
    act(() => store.set(source, null));
    expect(result.current).toEqual({ ...absent, order: null });
    act(() => store.set(source, hidden));
    expect(result.current.code).toBe("");
    act(() =>
      edit((tx) => {
        tx.deleteCell("c1");
        tx.deleteCell("c2");
      }),
    );
    expect(result.current).toEqual({ ...absent, order: [] });
  });

  it("preserves drafts across Strict Mode remounts until the session ends", () => {
    const { wrapper, controller, detached } = setup();
    const useProbe = () => ({
      code: useNotebookCellCode("c1"),
      edit: useNotebookDocumentEdit(),
    });
    const first = renderHook(useProbe, { wrapper, reactStrictMode: true });
    const edit = first.result.current.edit;
    act(() => edit((tx) => tx.setCode("c1", "strict mode edit")));
    expect(first.result.current.code).toBe("strict mode edit");
    first.unmount();
    expect(detached).not.toHaveBeenCalled();

    const second = renderHook(useProbe, { wrapper, reactStrictMode: true });
    expect(second.result.current.code).toBe("strict mode edit");
    act(() => edit((tx) => tx.setCode("c1", "same session")));
    expect(second.result.current.code).toBe("same session");
    second.unmount();
    controller.abort();
    expect(detached).toHaveBeenCalledOnce();
    const callback = vi.fn();
    edit(callback);
    expect(callback).not.toHaveBeenCalled();
  });

  it("switches reads and edits to the supplied model and store", () => {
    const first = setup();
    const second = setup(
      withCells(document("n2"), {
        c1: cell("c1", "second source", { notebook_id: "n2" }),
      }),
    );
    const seen = vi.fn();
    function Probe() {
      seen({
        code: useNotebookCellCode("c1"),
        edit: useNotebookDocumentEdit(),
      });
      return null;
    }
    const tree = ({ store, model }: typeof first) => (
      <Provider store={store}>
        <DocumentProvider model={model}>
          <Probe />
        </DocumentProvider>
      </Provider>
    );
    const { rerender } = render(tree(first));
    const oldEdit: ReturnType<typeof useNotebookDocumentEdit> =
      seen.mock.calls.at(-1)![0].edit;
    act(() => oldEdit((tx) => tx.setCode("c1", "first draft")));
    rerender(tree(second));
    act(() => first.controller.abort());
    expect(first.detached).toHaveBeenCalledOnce();
    const latest: {
      code: string | null | undefined;
      edit: ReturnType<typeof useNotebookDocumentEdit>;
    } = seen.mock.calls.at(-1)![0];
    expect(latest.code).toBe("second source");
    expect(latest.edit).not.toBe(oldEdit);
    act(() => latest.edit((tx) => tx.setCode("c1", "second draft")));
    expect(seen.mock.calls.at(-1)![0].code).toBe("second draft");
    const stale = vi.fn();
    oldEdit(stale);
    expect(stale).not.toHaveBeenCalled();
    seen.mockClear();
    act(() =>
      first.store.set(
        first.source,
        withCells(document(), {
          c1: cell("c1", "stale host"),
        }),
      ),
    );
    expect(seen).not.toHaveBeenCalled();
  });

  it("requires a document provider", () => {
    expect(() => renderHook(useNotebookDocumentEdit)).toThrow(
      "DocumentProvider",
    );
  });
});

/* Copyright 2026 Marimo. All rights reserved. */
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import {
  Profiler,
  startTransition,
  StrictMode,
  Suspense,
  useLayoutEffect,
  useState,
} from "react";
import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { useStateForKey } from "../useStateForKey";

describe("useStateForKey", () => {
  it("preserves edits for the same key and creates fresh state on key changes", () => {
    const initialize = vi.fn(() => new Set<string>());
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, initialize),
      { initialProps: { key: "first" } },
    );
    const initial = result.current[0];
    act(() => result.current[1](new Set(["expanded"])));
    rerender({ key: "first" });
    expect(result.current[0]).toEqual(new Set(["expanded"]));
    expect(initialize).toHaveBeenCalledOnce();

    rerender({ key: "second" });
    expect(result.current[0]).toEqual(new Set());
    expect(result.current[0]).not.toBe(initial);
    expect(initialize).toHaveBeenCalledTimes(2);

    rerender({ key: "first" });
    expect(result.current[0]).toEqual(new Set());
    expect(initialize).toHaveBeenCalledTimes(3);
  });

  it("preserves queued functional updates and ignores setters from another key", () => {
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => 0),
      { initialProps: { key: "first" } },
    );
    const oldSetter = result.current[1];
    act(() => {
      result.current[1]((value) => value + 1);
      result.current[1]((value) => value + 1);
    });
    expect(result.current[0]).toBe(2);

    rerender({ key: "second" });
    const staleUpdate = vi.fn(() => 99);
    act(() => oldSetter(staleUpdate));
    act(() => oldSetter(99));
    expect(result.current[0]).toBe(0);
    expect(staleUpdate).not.toHaveBeenCalled();
  });

  it("uses Object.is for NaN and signed zero keys", () => {
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => "initial"),
      { initialProps: { key: Number.NaN } },
    );
    act(() => result.current[1]("draft"));
    rerender({ key: Number.NaN });
    expect(result.current[0]).toBe("draft");

    rerender({ key: 0 });
    expect(result.current[0]).toBe("initial");
    act(() => result.current[1]("draft"));
    rerender({ key: -0 });
    expect(result.current[0]).toBe("initial");
  });

  it("stores function values without invoking them", () => {
    const initial = vi.fn();
    const changed = vi.fn();
    const { result, rerender } = renderHook(
      ({ key, value }) => useStateForKey(key, () => value),
      { initialProps: { key: "first", value: initial } },
    );
    expect(result.current[0]).toBe(initial);
    act(() => result.current[1](() => changed));
    expect(result.current[0]).toBe(changed);
    rerender({ key: "second", value: initial });
    expect(result.current[0]).toBe(initial);
    expect(initial).not.toHaveBeenCalled();
    expect(changed).not.toHaveBeenCalled();
  });

  it("uses a changed initializer only after the key changes", () => {
    const first = vi.fn(() => "first default");
    const second = vi.fn(() => "second default");
    const { result, rerender } = renderHook(
      ({ key, initialize }) => useStateForKey(key, initialize),
      { initialProps: { key: "A", initialize: first } },
    );
    act(() => result.current[1]("draft"));
    rerender({ key: "A", initialize: second });
    expect(result.current[0]).toBe("draft");
    expect(second).not.toHaveBeenCalled();
    rerender({ key: "B", initialize: second });
    expect(result.current[0]).toBe("second default");
    expect(second).toHaveBeenCalledOnce();
  });

  it("compares object keys by reference rather than their contents", () => {
    const key = { id: "A" };
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => 0),
      { initialProps: { key } },
    );
    act(() => result.current[1](1));
    rerender({ key });
    expect(result.current[0]).toBe(1);
    rerender({ key: { id: "A" } });
    expect(result.current[0]).toBe(0);
  });

  it("keeps setters stable for the same key and accepts old setters when that key returns", () => {
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => 0),
      { initialProps: { key: "A" } },
    );
    const setA = result.current[1];
    act(() => setA(1));
    rerender({ key: "A" });
    expect(result.current[1]).toBe(setA);
    rerender({ key: "B" });
    expect(result.current[1]).not.toBe(setA);
    act(() => setA(2));
    expect(result.current[0]).toBe(0);
    rerender({ key: "A" });
    act(() => setA(3));
    expect(result.current[0]).toBe(3);
  });

  it("retries the owner without rendering or committing stale state to children", () => {
    const onOwnerRender = vi.fn();
    const onChildRender = vi.fn();
    const onCommit = vi.fn();
    const onLayout = vi.fn();
    function Child({ owner, value }: { owner: string; value: string }) {
      onChildRender(owner, value);
      useLayoutEffect(() => onLayout(owner, value), [owner, value]);
      return <span>{value}</span>;
    }
    function Owner({ owner }: { owner: string }) {
      onOwnerRender();
      const [value, setValue] = useStateForKey(owner, () => `${owner} default`);
      return (
        <>
          <button onClick={() => setValue("draft")}>Edit</button>
          <Child owner={owner} value={value} />
        </>
      );
    }
    const content = (owner: string) => (
      <Profiler id="owner" onRender={onCommit}>
        <Owner owner={owner} />
      </Profiler>
    );
    const { rerender } = render(content("A"));
    const button = screen.getByRole("button", { name: "Edit" });
    fireEvent.click(button);
    expect(screen.getByText("draft")).toBeInTheDocument();
    onOwnerRender.mockClear();
    onChildRender.mockClear();
    onCommit.mockClear();
    onLayout.mockClear();

    rerender(content("B"));
    expect(onOwnerRender.mock.calls.length).toBeGreaterThan(1);
    expect(onChildRender.mock.calls).toEqual([["B", "B default"]]);
    expect(onLayout.mock.calls).toEqual([["B", "B default"]]);
    expect(onCommit).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Edit" })).toBe(button);
  });

  it("keeps state correct when Strict Mode repeats initialization and updates", () => {
    const initialize = vi.fn(() => new Set<string>());
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, initialize),
      { initialProps: { key: "A" }, wrapper: StrictMode },
    );
    expect(initialize.mock.calls.length).toBeGreaterThan(1);
    act(() => result.current[1]((previous) => new Set([...previous, "draft"])));
    expect(result.current[0]).toEqual(new Set(["draft"]));
    rerender({ key: "B" });
    expect(result.current[0]).toEqual(new Set());
  });

  it.each(["completes", "is canceled"])(
    "preserves visible edits when a suspended transition %s",
    async (outcome) => {
      const pending = new Deferred<void>();
      let blocked = true;
      const suspended = vi.fn();
      function Pending({ owner }: { owner: string }) {
        if (owner === "B" && blocked) {
          suspended();
          throw pending.promise;
        }
        return null;
      }
      function Owner({ owner }: { owner: string }) {
        const [value, setValue] = useStateForKey(owner, () => 0);
        return (
          <>
            <button onClick={() => setValue((previous) => previous + 1)}>
              {owner}:{value}
            </button>
            <Pending owner={owner} />
          </>
        );
      }
      function Harness() {
        const [owner, setOwner] = useState("A");
        return (
          <>
            <button onClick={() => startTransition(() => setOwner("B"))}>
              Switch owner
            </button>
            <button onClick={() => setOwner("A")}>Keep owner</button>
            <Suspense fallback="Loading">
              <Owner owner={owner} />
            </Suspense>
          </>
        );
      }
      render(<Harness />);
      fireEvent.click(screen.getByRole("button", { name: "A:0" }));
      fireEvent.click(screen.getByRole("button", { name: "Switch owner" }));
      expect(suspended).toHaveBeenCalled();
      fireEvent.click(screen.getByRole("button", { name: "A:1" }));
      expect(screen.getByRole("button", { name: "A:2" })).toBeInTheDocument();
      if (outcome === "is canceled") {
        fireEvent.click(screen.getByRole("button", { name: "Keep owner" }));
      }
      await act(async () => {
        blocked = false;
        pending.resolve();
        await pending.promise;
      });
      expect(
        screen.getByRole("button", {
          name: outcome === "completes" ? "B:0" : "A:2",
        }),
      ).toBeInTheDocument();
    },
  );
});

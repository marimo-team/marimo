/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import type { IPluginProps } from "../../types";
import { LazyPlugin } from "../LazyPlugin";

const intersection = vi.hoisted(() => ({
  entry: null as { isIntersecting: boolean } | null,
}));

vi.mock("@uidotdev/usehooks", () => ({
  useIntersectionObserver: () => [vi.fn(), intersection.entry],
}));

type Props = IPluginProps<
  boolean,
  { showLoadingIndicator: boolean },
  { load: (req: {}) => Promise<{ html: string }> }
>;

function renderLazy(value: boolean, setValue: Props["setValue"]) {
  const load = vi.fn().mockResolvedValue({ html: "<p>loaded</p>" });
  const props: Props = {
    value,
    setValue,
    data: { showLoadingIndicator: false },
    functions: { load },
    host: document.createElement("div"),
  };
  return render(<>{LazyPlugin.render(props)}</>);
}

describe("LazyPlugin visibility", () => {
  afterEach(() => {
    intersection.entry = null;
  });

  test("does not change the value while hidden", () => {
    intersection.entry = { isIntersecting: false };
    const setValue = vi.fn();
    renderLazy(false, setValue);
    expect(setValue).not.toHaveBeenCalled();
  });

  test("marks the plugin loaded once when it becomes visible", () => {
    intersection.entry = { isIntersecting: true };
    const setValue = vi.fn();
    renderLazy(false, setValue);
    expect(setValue).toHaveBeenCalledTimes(1);
    expect(setValue).toHaveBeenCalledWith(true);
  });

  test("does not change an already loaded value", () => {
    intersection.entry = { isIntersecting: true };
    const setValue = vi.fn();
    renderLazy(true, setValue);
    expect(setValue).not.toHaveBeenCalled();
  });

  test("calls the setter after render, never during it", () => {
    intersection.entry = { isIntersecting: true };
    let renderCount = 0;
    const calls: number[] = [];
    const setValue = vi.fn(() => calls.push(renderCount));
    const Probe = () => {
      renderCount++;
      return null;
    };
    const load = vi.fn().mockResolvedValue({ html: "" });
    render(
      <>
        {LazyPlugin.render({
          value: false,
          setValue,
          data: { showLoadingIndicator: false },
          functions: { load },
          host: document.createElement("div"),
        })}
        <Probe />
      </>,
    );
    // A render-time call happens before the sibling Probe renders (count 0).
    // An effect runs after the whole tree commits (count 1).
    expect(calls).toEqual([1]);
  });
});

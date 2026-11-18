/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copyToClipboard } from "@/utils/copy";
import { CopyClipboardIcon } from "../copy-icon";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

describe("CopyClipboardIcon", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows copy confirmation for two seconds", async () => {
    const { getByRole, container } = render(
      <CopyClipboardIcon value="copied text" tooltip={false} />,
    );
    await act(async () => {
      fireEvent.click(getByRole("button"));
    });
    expect(copyToClipboard).toHaveBeenCalledWith("copied text");
    expect(container.querySelector(".lucide-check")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1999));
    expect(container.querySelector(".lucide-check")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(container.querySelector(".lucide-copy")).toBeInTheDocument();
  });

  it("releases the pending confirmation reset when unmounted", async () => {
    const { getByRole, unmount } = render(
      <CopyClipboardIcon value="text" tooltip={false} />,
    );
    await act(async () => {
      fireEvent.click(getByRole("button"));
    });
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not schedule a reset if the clipboard finishes after unmount", async () => {
    let finishCopy: (() => void) | undefined;
    vi.mocked(copyToClipboard).mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finishCopy = resolve;
        }),
    );
    const { getByRole, unmount } = render(
      <CopyClipboardIcon value="text" tooltip={false} />,
    );
    fireEvent.click(getByRole("button"));
    unmount();
    await act(async () => finishCopy?.());
    expect(vi.getTimerCount()).toBe(0);
  });
});

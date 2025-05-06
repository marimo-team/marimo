/* Copyright 2024 Marimo. All rights reserved. */
import { renderHook, act, render } from "@testing-library/react";
import { useResizeHandle } from "../useResizeHandle";
import { describe, it, expect, vi } from "vitest";

describe("useResizeHandle", () => {
  it("should initialize with correct refs and style", () => {
    const { result } = renderHook(() =>
      useResizeHandle({
        startingWidth: 500,
        onResize: vi.fn(),
        direction: "right",
      }),
    );

    expect(result.current.resizableDivRef.current).toBeNull();
    expect(result.current.handleRef.current).toBeNull();
    expect(result.current.style).toEqual({ width: "500px" });
  });

  it("should handle contentWidth starting width", () => {
    const { result } = renderHook(() =>
      useResizeHandle({
        startingWidth: "contentWidth",
        onResize: vi.fn(),
        direction: "right",
      }),
    );

    expect(result.current.style).toEqual({
      width: "var(--content-width-medium)",
    });
  });

  it("should call onResize when resizing ends", () => {
    const onResize = vi.fn();

    // Create a test component that uses the hook
    const TestComponent = () => {
      const { resizableDivRef, handleRef } = useResizeHandle({
        startingWidth: 500,
        onResize,
        direction: "right",
      });

      return (
        <div>
          <div
            ref={resizableDivRef}
            style={{ width: "500px" }}
            data-testid="resizable-div"
          />
          <div ref={handleRef} data-testid="handle" />
        </div>
      );
    };

    const { getByTestId } = render(<TestComponent />);
    const resizableDiv = getByTestId("resizable-div") as HTMLDivElement;
    const handle = getByTestId("handle") as HTMLDivElement;

    // Simulate resize
    act(() => {
      const mousedownEvent = new MouseEvent("mousedown", { clientX: 0 });
      handle.dispatchEvent(mousedownEvent);

      const mousemoveEvent = new MouseEvent("mousemove", { clientX: 100 });
      document.dispatchEvent(mousemoveEvent);

      const mouseupEvent = new MouseEvent("mouseup");
      document.dispatchEvent(mouseupEvent);
    });

    expect(resizableDiv.style.width).toBe("600px"); // 500px + 100px movement
    expect(onResize).toHaveBeenCalledWith(600);
  });

  it("should handle left direction resizing", () => {
    const onResize = vi.fn();

    // Create a test component that uses the hook
    const TestComponent = () => {
      const { resizableDivRef, handleRef } = useResizeHandle({
        startingWidth: 500,
        onResize,
        direction: "left",
      });

      return (
        <div>
          <div
            ref={resizableDivRef}
            style={{ width: "500px" }}
            data-testid="resizable-div"
          />
          <div ref={handleRef} data-testid="handle" />
        </div>
      );
    };

    const { getByTestId } = render(<TestComponent />);

    const resizableDiv = getByTestId("resizable-div") as HTMLDivElement;
    const handle = getByTestId("handle") as HTMLDivElement;

    // Simulate resize
    act(() => {
      const mousedownEvent = new MouseEvent("mousedown", { clientX: 0 });
      handle.dispatchEvent(mousedownEvent);

      const mousemoveEvent = new MouseEvent("mousemove", { clientX: -100 });
      document.dispatchEvent(mousemoveEvent);

      const mouseupEvent = new MouseEvent("mouseup");
      document.dispatchEvent(mouseupEvent);
    });

    expect(resizableDiv.style.width).toBe("600px"); // 500px - (-100px) movement
    expect(onResize).toHaveBeenCalledWith(600);
  });
});

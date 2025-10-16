/* Copyright 2024 Marimo. All rights reserved. */

import { useRef, useState } from "react";
import { isInVscodeExtension } from "@/core/vscode/is-in-vscode";
import { useEventListener } from "@/hooks/useEventListener";

/**
 * Get the full screen element if we are in full screen mode
 */
export function useFullScreenElement() {
  const [fullScreenElement, setFullScreenElement] = useState<Element | null>(
    document.fullscreenElement,
  );
  useEventListener(document, "fullscreenchange", () => {
    setFullScreenElement(document.fullscreenElement);
  });
  return fullScreenElement;
}

/**
 * HOC wrapping a Portal component to use the
 * full screen element as the container if we are in full screen mode
 */
export function withFullScreenAsRoot<
  T extends {
    container?: Element | DocumentFragment | null;
  },
>(Component: React.ComponentType<T>) {
  console.warn("[debug] Component", Component);

  const FindClosestVscodeOutputContainer = (props: T) => {
    const el = useRef<HTMLDivElement>(null);
    const [, setMounted] = useState(false);
    console.warn("[debug] el.current", el.current);
    if (!el.current) {
      return (
        <>
          <div
            ref={(element) => {
              setMounted(true);
              el.current = element;
            }}
            className="contents invisible"
          />
          <span>should not show this...</span>
        </>
      );
    }

    const closest = closestThroughShadowDOMs(
      el.current,
      "[data-vscode-output-container]",
    );
    console.warn(
      "[debug] el.current.closest('[data-vscode-output-container]')",
      "el.current.closest('[data-vscode-output-container]')",
      closest,
    );

    return (
      <>
        <div ref={el} className="contents invisible" />
        <Component {...props} container={closest} />
      </>
    );
  };

  const Comp = (props: T) => {
    // If we are in the VSCode extension, we use the VSCode output container
    const vscodeOutputContainer = isInVscodeExtension();
    console.warn("[debug] vscodeOutputContainer", vscodeOutputContainer);
    if (vscodeOutputContainer) {
      return <FindClosestVscodeOutputContainer {...props} />;
    }

    const fullScreenElement = useFullScreenElement();
    if (!fullScreenElement) {
      return <Component {...props} />;
    }

    return <Component {...props} container={fullScreenElement} />;
  };

  Comp.displayName = Component.displayName;
  return Comp;
}

function closestThroughShadowDOMs(
  element: Element,
  selector: string,
): Element | null {
  let currentElement: Element | null = element;

  while (currentElement) {
    const cellElement = currentElement.closest(selector);
    if (cellElement) {
      return cellElement;
    }

    const root = currentElement.getRootNode();
    currentElement =
      root instanceof ShadowRoot ? root.host : currentElement.parentElement;

    if (currentElement === root) {
      break;
    }
  }

  return null;
}

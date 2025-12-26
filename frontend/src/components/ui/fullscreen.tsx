/* Copyright 2026 Marimo. All rights reserved. */

import type { PopoverContentProps } from "@radix-ui/react-popover";
import React, { useState } from "react";
import { isInVscodeExtension } from "@/core/vscode/is-in-vscode";
import { useEventListener } from "@/hooks/useEventListener";

const VSCODE_OUTPUT_CONTAINER_SELECTOR = "[data-vscode-output-container]";

// vscode has smaller viewport so we need all the max-height we can get.
// Otherwise, we give a 30px buffer to the max-height.
export const MAX_HEIGHT_OFFSET = isInVscodeExtension() ? 0 : 30;

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
  const FindClosestVscodeOutputContainer = (props: T) => {
    const [closest, setClosest] = React.useState<Element | null>(null);
    const el = React.useRef<HTMLDivElement>(null);

    React.useLayoutEffect(() => {
      if (!el.current) {
        return;
      }

      const found = closestThroughShadowDOMs(
        el.current,
        VSCODE_OUTPUT_CONTAINER_SELECTOR,
      );
      setClosest(found);
    }, []);

    return (
      <>
        <div ref={el} className="contents invisible" />
        <Component {...props} container={closest} />
      </>
    );
  };

  const Comp = (props: T) => {
    const fullScreenElement = useFullScreenElement();

    // If we are in the VSCode extension, we use the VSCode output container
    const vscodeOutputContainer = isInVscodeExtension();
    if (vscodeOutputContainer) {
      return <FindClosestVscodeOutputContainer {...props} />;
    }

    if (!fullScreenElement) {
      return <Component {...props} />;
    }

    return <Component {...props} container={fullScreenElement} />;
  };

  Comp.displayName = Component.displayName;
  return Comp;
}

/**
 * HOC wrapping a PortalContent component to set a better collision boundary,
 * when inside vscode.
 */
export function withSmartCollisionBoundary<
  T extends {
    collisionBoundary?: PopoverContentProps["collisionBoundary"];
  },
>(Component: React.ComponentType<T>) {
  const FindClosestVscodeOutputContainer = (props: T) => {
    const [closest, setClosest] = React.useState<Element | null>(null);
    const el = React.useRef<HTMLDivElement>(null);

    React.useLayoutEffect(() => {
      if (!el.current) {
        return;
      }

      const found = closestThroughShadowDOMs(
        el.current,
        VSCODE_OUTPUT_CONTAINER_SELECTOR,
      );
      setClosest(found);
    }, []);

    return (
      <>
        <div ref={el} className="contents invisible" />
        <Component {...props} collisionBoundary={closest} />
      </>
    );
  };

  const Comp = (props: T) => {
    // If we are in the VSCode extension, we use the VSCode output container
    const vscodeOutputContainer = isInVscodeExtension();
    if (vscodeOutputContainer) {
      return <FindClosestVscodeOutputContainer {...props} />;
    }

    return <Component {...props} />;
  };

  Comp.displayName = Component.displayName;
  return Comp;
}

/**
 * Find the closest element (with .closest), but through shadow DOMs.
 */
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

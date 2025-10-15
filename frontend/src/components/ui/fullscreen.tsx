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
    console.warn("[debug] el.current", el.current);
    if (!el.current) {
      return (
        <>
          <div ref={el} className="contents invisible" />
          <span>Loading...</span>
        </>
      );
    }

    console.warn(
      "[debug] el.current.closest('[data-vscode-output-container]')",
      "el.current.closest('[data-vscode-output-container]')",
      el.current.closest("[data-vscode-output-container]"),
    );

    return (
      <>
        <div ref={el} className="contents invisible" />
        <Component
          {...props}
          container={el.current.closest("[data-vscode-output-container]")}
        />
      </>
    );
  };

  const Comp = (props: T) => {
    const fullScreenElement = useFullScreenElement();
    if (!fullScreenElement) {
      return <Component {...props} />;
    }

    // If we are in the VSCode extension, we use the VSCode output container
    const vscodeOutputContainer = isInVscodeExtension();
    console.warn("[debug] vscodeOutputContainer", vscodeOutputContainer);
    if (vscodeOutputContainer) {
      return <FindClosestVscodeOutputContainer {...props} />;
    }

    return <Component {...props} container={fullScreenElement} />;
  };

  Comp.displayName = Component.displayName;
  return Comp;
}

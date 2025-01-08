/* Copyright 2024 Marimo. All rights reserved. */
import { useEventListener } from "@/hooks/useEventListener";
import { useState } from "react";

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
    container?: HTMLElement | null;
  },
>(Component: React.ComponentType<T>) {
  const Comp = (props: T) => {
    const fullScreenElement = useFullScreenElement();
    if (!fullScreenElement) {
      return <Component {...props} />;
    }
    return <Component {...props} container={fullScreenElement} />;
  };

  Comp.displayName = Component.displayName;
  return Comp;
}

/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useState } from "react";

type Event = Partial<Pick<React.MouseEvent, "stopPropagation">>;

export function useBoolean(initialState: boolean) {
  const [state, setState] = useState(initialState);

  return [
    state,
    {
      setTrue: useCallback((evt?: Event) => {
        evt?.stopPropagation?.();
        setState(true);
      }, []),
      setFalse: useCallback((evt?: Event) => {
        evt?.stopPropagation?.();
        setState(false);
      }, []),
      toggle: useCallback((evt?: Event) => {
        evt?.stopPropagation?.();
        setState((prev) => !prev);
      }, []),
    },
  ] as const;
}

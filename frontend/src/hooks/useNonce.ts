/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useState } from "react";

export function useNonce() {
  // eslint-disable-next-line react/hook-use-state
  const [, setNonce] = useState(0);
  return useCallback(() => {
    setNonce((n) => n + 1);
  }, []);
}

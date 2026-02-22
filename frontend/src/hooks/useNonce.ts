/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useState } from "react";

export function useNonce() {
  const [, setNonce] = useState(0);
  return useCallback(() => {
    setNonce((n) => n + 1);
  }, []);
}

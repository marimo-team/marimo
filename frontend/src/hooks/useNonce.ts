/* Copyright 2026 Marimo. All rights reserved. */
import { useState, useCallback } from "react";

export function useNonce() {
  const [, setNonce] = useState(0);
  return useCallback(() => {
    setNonce((n: number) => n + 1);
  }, []);
}

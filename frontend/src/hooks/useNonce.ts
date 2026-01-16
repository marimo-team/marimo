/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useState } from "react";

export function useNonce() {
  const [_nonce, setNonce] = useState(0);
  return useCallback(() => {
    setNonce((n: number) => n + 1);
  }, []);
}

/* Copyright 2024 Marimo. All rights reserved. */
import { useState } from "react";

export function useNonce() {
  const [nonce, setNonce] = useState(0);
  return () => {
    setNonce(nonce + 1);
  };
}

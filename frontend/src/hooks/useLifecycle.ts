/* Copyright 2023 Marimo. All rights reserved. */
import { EffectCallback, useEffect } from "react";

/**
 * Wrapper around useEffect that makes it clearer that the effect is run, just on mount.
 */
export function useOnMount(effect: EffectCallback) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(effect, []);
}

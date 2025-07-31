/* Copyright 2024 Marimo. All rights reserved. */
import { type EffectCallback, useEffect } from "react";

/**
 * Wrapper around useEffect that makes it clearer that the effect is run, just on mount.
 */
export function useOnMount(effect: EffectCallback) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(effect, []);
}

/**
 * Wrapper around useEffect that makes it clearer that the effect is run, just on unmount.
 */
export function useOnUnmount(effect: EffectCallback) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    return effect();
  }, []);
}

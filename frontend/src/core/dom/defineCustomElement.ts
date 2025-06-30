/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "../../utils/Logger";

/**
 * Wrapper for the customElements.define() method to add safety checks.
 */
export function defineCustomElement(
  name: string,
  clazz: CustomElementConstructor,
) {
  if (!globalThis?.customElements) {
    Logger.warn("Custom elements not supported");
    return;
  }

  if (globalThis.customElements.get(name)) {
    if (import.meta.env.PROD) {
      Logger.warn(`Custom element ${name} already defined`);
    }
    return;
  }
  globalThis.customElements.define(name, clazz);
}

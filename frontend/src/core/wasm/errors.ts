/* Copyright 2026 Marimo. All rights reserved. */

export class WasmInitializationError extends Error {
  public constructor(cause: Error) {
    super(cause.message, { cause });
    this.name = "WasmInitializationError";
  }
}

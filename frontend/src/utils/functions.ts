/* Copyright 2023 Marimo. All rights reserved. */
export const Functions = {
  NOOP: () => {
    return;
  },
  THROW: () => {
    throw new Error("Should not be called");
  },
};

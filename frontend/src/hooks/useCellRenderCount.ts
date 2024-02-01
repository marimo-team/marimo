/* Copyright 2024 Marimo. All rights reserved. */
export function useCellRenderCount() {
  return {
    countRender: () => {
      if (process.env.NODE_ENV !== "test") {
        return;
      }

      const currentCount = Number.parseInt(
        document.body.dataset.cellRenderCount || "0",
      );
      document.body.dataset.cellRenderCount = (currentCount + 1).toString();
    },
  };
}

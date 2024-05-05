/* Copyright 2024 Marimo. All rights reserved. */
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { useEffect } from "react";
import { useReactFlow, useStore } from "reactflow";

/**
 * Call fitToView whenever the dimensions changes
 */
export function useFitToViewOnDimensionChange() {
  const instance = useReactFlow();
  const width = useStore(({ width }) => width);
  const height = useStore(({ height }) => height);
  const debounceFitView = useDebouncedCallback(() => {
    instance.fitView({ duration: 100 });
  }, 100);

  // When the window is resized, fit the view to the graph.
  useEffect(() => {
    if (!width || !height) {
      return;
    }
    debounceFitView();
  }, [width, height, debounceFitView]);
}

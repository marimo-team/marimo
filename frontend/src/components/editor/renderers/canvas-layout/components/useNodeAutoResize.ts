/* Copyright 2024 Marimo. All rights reserved. */

import { useReactFlow, useUpdateNodeInternals } from "@xyflow/react";
import { useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { useDebounce, useDebouncedCallback } from "@/hooks/useDebounce";
import { useResizeObserver } from "@/hooks/useResizeObserver";

/** Layout constants for node height calculations */
const LAYOUT = {
  MIN_OUTPUT_HEIGHT: 60,
  TOOLBAR_HEIGHT: 0,
  FOOTER_HEIGHT: 28,
  BORDER_PADDING: 0,
} as const;

interface UseNodeAutoResizeOptions {
  /** The react-flow node ID */
  nodeId: string | undefined;
  /** Whether the cell has output */
  hasOutput: boolean;
  /** Current editor height */
  editorHeight: number;
}

interface UseNodeAutoResizeResult {
  /** Ref to attach to the output container */
  outputRef: React.RefObject<HTMLDivElement | null>;
  /** The total calculated height of the node */
  totalHeight: number;
  /** Callback to handle resize start from NodeResizer */
  handleResizeStart: () => void;
  /** Callback to handle resize from NodeResizer */
  handleResize: () => void;
  /** Callback to handle resize end from NodeResizer */
  handleResizeEnd: () => void;
  /** Callback to trigger resize on language mode change */
  handleLanguageChange: () => void;
  /** Callback to trigger resize on console output change */
  handleConsoleOutputChange: () => void;
  /** Callback to manually trigger a resize recalculation */
  triggerResize: () => void;
  /** Minimum height for the output area */
  minOutputHeight: number;
  /** Footer height constant */
  footerHeight: number;
}

/**
 * Measures the actual content height from an output container element.
 * Falls back to the container height if no child element exists.
 */
function measureContentHeight(
  outputElement: HTMLDivElement | null,
  fallbackHeight: number,
): number {
  if (!outputElement) {
    return fallbackHeight;
  }

  const contentElement = outputElement.firstElementChild;
  if (contentElement) {
    return (contentElement as HTMLElement).offsetHeight;
  }

  return fallbackHeight;
}

/**
 * Calculates the total node height based on component heights.
 */
function calculateNodeHeight(
  editorHeight: number,
  outputHeight: number,
  hasOutput: boolean,
): number {
  const baseHeight =
    editorHeight +
    LAYOUT.TOOLBAR_HEIGHT +
    LAYOUT.FOOTER_HEIGHT +
    LAYOUT.BORDER_PADDING;

  if (hasOutput) {
    return baseHeight + Math.max(outputHeight, LAYOUT.MIN_OUTPUT_HEIGHT);
  }

  return baseHeight;
}

/**
 * Hook to track output height via ResizeObserver.
 */
function useOutputHeightTracker(
  outputRef: React.RefObject<HTMLDivElement | null>,
) {
  const [actualHeight, setActualHeight] = useState(0);

  useResizeObserver({
    ref: outputRef,
    onResize: (size) => {
      if (size.height) {
        setActualHeight(size.height);
      }
    },
  });

  return actualHeight;
}

/**
 * Hook to update node dimensions in react-flow.
 */
function useNodeDimensionUpdater(nodeId: string | undefined) {
  const { setNodes } = useReactFlow();

  const updateNodeHeight = useEvent((targetHeight: number) => {
    if (!nodeId) {
      return;
    }

    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            style: {
              ...node.style,
              height: targetHeight,
            },
            height: targetHeight,
          };
        }
        return node;
      }),
    );
  });

  return updateNodeHeight;
}

interface AutoResizeOptions {
  nodeId: string | undefined;
  hasOutput: boolean;
  editorHeight: number;
  debouncedOutputHeight: number;
  outputRef: React.RefObject<HTMLDivElement | null>;
  updateNodeHeight: (height: number) => void;
}

/**
 * Hook to auto-resize when output content changes (debounced).
 */
function useAutoResizeOnOutputChange(options: AutoResizeOptions) {
  const {
    nodeId,
    hasOutput,
    editorHeight,
    debouncedOutputHeight,
    outputRef,
    updateNodeHeight,
  } = options;

  useEffect(() => {
    // Skip if editor hasn't been measured yet (ensures min height = editor + footer)
    if (
      !nodeId ||
      !hasOutput ||
      debouncedOutputHeight === 0 ||
      editorHeight === 0
    ) {
      return;
    }

    const measuredHeight = measureContentHeight(
      outputRef.current,
      debouncedOutputHeight,
    );
    const targetHeight = calculateNodeHeight(
      editorHeight,
      measuredHeight,
      true,
    );
    updateNodeHeight(targetHeight);
  }, [
    nodeId,
    hasOutput,
    editorHeight,
    debouncedOutputHeight,
    outputRef,
    updateNodeHeight,
  ]);
}

/**
 * Hook to auto-resize when editor height changes and there's no output.
 */
function useResizeOnEditorHeightChange(options: {
  nodeId: string | undefined;
  hasOutput: boolean;
  editorHeight: number;
  updateNodeHeight: (height: number) => void;
}) {
  const { nodeId, hasOutput, editorHeight, updateNodeHeight } = options;

  useEffect(() => {
    // Only resize when there's no output and editor height is measured
    if (!nodeId || hasOutput || editorHeight === 0) {
      return;
    }

    // When no output, node height = editor + footer
    const targetHeight = calculateNodeHeight(editorHeight, 0, false);
    updateNodeHeight(targetHeight);
  }, [nodeId, hasOutput, editorHeight, updateNodeHeight]);
}

interface ResizeOnOutputAppearOptions {
  nodeId: string | undefined;
  hasOutput: boolean;
  editorHeight: number;
  outputRef: React.RefObject<HTMLDivElement | null>;
  updateNodeHeight: (height: number) => void;
}

/**
 * Hook to resize when transitioning from no output to having output.
 */
function useResizeOnOutputAppear(options: ResizeOnOutputAppearOptions) {
  const { nodeId, hasOutput, editorHeight, outputRef, updateNodeHeight } =
    options;
  const prevHasOutputRef = useRef(hasOutput);

  useEffect(() => {
    const prevHasOutput = prevHasOutputRef.current;
    prevHasOutputRef.current = hasOutput;

    // Detect transition from no output to having output
    // Skip if editor hasn't been measured yet (ensures min height = editor + footer)
    if (!prevHasOutput && hasOutput && nodeId && editorHeight > 0) {
      // Small delay to let the output render before measuring
      const timeoutId = setTimeout(() => {
        const measuredHeight = measureContentHeight(
          outputRef.current,
          LAYOUT.MIN_OUTPUT_HEIGHT,
        );
        const targetHeight = calculateNodeHeight(
          editorHeight,
          Math.max(measuredHeight, LAYOUT.MIN_OUTPUT_HEIGHT),
          true,
        );
        updateNodeHeight(targetHeight);
      }, 50);

      return () => clearTimeout(timeoutId);
    }
  }, [nodeId, hasOutput, editorHeight, outputRef, updateNodeHeight]);
}

/**
 * Hook to update react-flow node internals when height changes.
 */
function useNodeInternalsSync(nodeId: string | undefined, totalHeight: number) {
  const updateNodeInternals = useUpdateNodeInternals();

  useEffect(() => {
    if (nodeId && totalHeight > 0) {
      updateNodeInternals(nodeId);
    }
  }, [nodeId, totalHeight, updateNodeInternals]);
}

interface InitialResizeOptions {
  nodeId: string | undefined;
  hasOutput: boolean;
  editorHeight: number;
  outputRef: React.RefObject<HTMLDivElement | null>;
  updateNodeHeight: (height: number) => void;
}

/**
 * Hook to run an initial resize check on mount (debounced).
 * This ensures the node has the correct size when first rendered.
 */
function useInitialResize(options: InitialResizeOptions) {
  const { nodeId, hasOutput, editorHeight, outputRef, updateNodeHeight } =
    options;
  const hasInitializedRef = useRef(false);

  useEffect(() => {
    // Only run once on mount, and wait until editor has been measured
    if (hasInitializedRef.current || !nodeId || editorHeight === 0) {
      return;
    }

    // Debounce the initial resize to let content render
    const timeoutId = setTimeout(() => {
      hasInitializedRef.current = true;

      const measuredHeight = measureContentHeight(
        outputRef.current,
        LAYOUT.MIN_OUTPUT_HEIGHT,
      );
      const targetHeight = calculateNodeHeight(
        editorHeight,
        hasOutput ? Math.max(measuredHeight, LAYOUT.MIN_OUTPUT_HEIGHT) : 0,
        hasOutput,
      );
      updateNodeHeight(targetHeight);
    }, 200);

    return () => clearTimeout(timeoutId);
  }, [nodeId, hasOutput, editorHeight, outputRef, updateNodeHeight]);
}

/**
 * Hook to create a shared resize trigger that measures and updates node height.
 * This is used by multiple resize scenarios (language change, console output, etc.)
 */
function useResizeTrigger(
  nodeId: string | undefined,
  hasOutput: boolean,
  editorHeight: number,
  outputRef: React.RefObject<HTMLDivElement | null>,
  updateNodeHeight: (height: number) => void,
) {
  return useEvent(() => {
    if (!nodeId || editorHeight === 0) {
      return;
    }

    const measuredHeight = measureContentHeight(
      outputRef.current,
      LAYOUT.MIN_OUTPUT_HEIGHT,
    );
    const targetHeight = calculateNodeHeight(
      editorHeight,
      hasOutput ? Math.max(measuredHeight, LAYOUT.MIN_OUTPUT_HEIGHT) : 0,
      hasOutput,
    );
    updateNodeHeight(targetHeight);
  });
}

/**
 * Hook to handle language mode changes with a small delay for panel rendering.
 */
function useResizeOnLanguageChange(resizeTrigger: () => void) {
  return useEvent(() => {
    // 50ms delay for language panel to render
    setTimeout(resizeTrigger, 50);
  });
}

/**
 * Hook to handle console output changes with debouncing.
 */
function useResizeOnConsoleChange(resizeTrigger: () => void) {
  // 200ms debounce for console output changes
  return useDebouncedCallback(resizeTrigger, 200);
}

/**
 * Custom hook that manages automatic node resizing based on output content.
 *
 * This hook handles:
 * - Tracking actual output height via ResizeObserver
 * - Debounced auto-resize when output content changes (200ms)
 * - Resize on editor height changes (immediate when no output)
 * - Resize on transition from no output to having output
 * - Manual resize end handler for NodeResizer component
 * - Syncing node internals when dimensions change
 * - Language mode changes (50ms delay)
 * - Console output changes (200ms debounce)
 */
export function useNodeAutoResize({
  nodeId,
  hasOutput,
  editorHeight,
}: UseNodeAutoResizeOptions): UseNodeAutoResizeResult {
  const outputRef = useRef<HTMLDivElement>(null);
  const { getNodes, setNodes } = useReactFlow();

  // Track initial dimensions of selected nodes for multi-node resizing
  const initialDimensionsRef = useRef<
    Map<string, { width: number; height: number }>
  >(new Map());

  // Track actual output height
  const actualOutputHeight = useOutputHeightTracker(outputRef);

  // Debounce to avoid flickering during rapid changes
  const debouncedOutputHeight = useDebounce(actualOutputHeight, 200);

  // Calculate total node height
  const totalHeight = calculateNodeHeight(
    editorHeight,
    actualOutputHeight,
    hasOutput,
  );

  // Setup node dimension updater
  const updateNodeHeight = useNodeDimensionUpdater(nodeId);

  // Create shared resize trigger for language and console changes
  const resizeTrigger = useResizeTrigger(
    nodeId,
    hasOutput,
    editorHeight,
    outputRef,
    updateNodeHeight,
  );
  const handleLanguageChange = useResizeOnLanguageChange(resizeTrigger);
  const handleConsoleOutputChange = useResizeOnConsoleChange(resizeTrigger);

  // Sync node internals when height changes
  useNodeInternalsSync(nodeId, totalHeight);

  // Auto-resize on debounced output changes
  useAutoResizeOnOutputChange({
    nodeId,
    hasOutput,
    editorHeight,
    debouncedOutputHeight,
    outputRef,
    updateNodeHeight,
  });

  // Auto-resize on editor height changes when there's no output
  useResizeOnEditorHeightChange({
    nodeId,
    hasOutput,
    editorHeight,
    updateNodeHeight,
  });

  // Resize when output first appears
  useResizeOnOutputAppear({
    nodeId,
    hasOutput,
    editorHeight,
    outputRef,
    updateNodeHeight,
  });

  // Initial resize on mount (debounced)
  useInitialResize({
    nodeId,
    hasOutput,
    editorHeight,
    outputRef,
    updateNodeHeight,
  });

  // Handle resize start - capture initial dimensions of all selected nodes
  const handleResizeStart = useEvent(() => {
    if (!nodeId) {
      return;
    }

    const nodes = getNodes();
    const selectedNodes = nodes.filter((node) => node.selected);

    // If multiple nodes are selected, capture their initial dimensions
    if (selectedNodes.length > 1) {
      initialDimensionsRef.current = new Map(
        selectedNodes.map((node) => [
          node.id,
          {
            width: node.width || node.measured?.width || 600,
            height: node.height || node.measured?.height || 60,
          },
        ]),
      );
    } else {
      initialDimensionsRef.current.clear();
    }
  });

  // Handle resize - apply proportional resizing to all selected nodes
  const handleResize = useEvent(() => {
    if (!nodeId || initialDimensionsRef.current.size === 0) {
      return;
    }

    const nodes = getNodes();
    const currentNode = nodes.find((node) => node.id === nodeId);
    if (!currentNode) {
      return;
    }

    const initialDimensions = initialDimensionsRef.current.get(nodeId);
    if (!initialDimensions) {
      return;
    }

    const currentWidth =
      currentNode.width || currentNode.measured?.width || 600;
    const currentHeight =
      currentNode.height || currentNode.measured?.height || 60;

    // Calculate scale factors
    const widthScale = currentWidth / initialDimensions.width;
    const heightScale = currentHeight / initialDimensions.height;

    // Apply the same scale to all selected nodes
    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === nodeId || !node.selected) {
          return node;
        }

        const nodeDimensions = initialDimensionsRef.current.get(node.id);
        if (!nodeDimensions) {
          return node;
        }

        const newWidth = nodeDimensions.width * widthScale;
        const newHeight = nodeDimensions.height * heightScale;

        return {
          ...node,
          style: {
            ...node.style,
            width: newWidth,
            height: newHeight,
          },
          width: newWidth,
          height: newHeight,
        };
      }),
    );
  });

  // Handle manual resize end from NodeResizer
  const handleResizeEnd = useEvent(() => {
    if (!nodeId) {
      return;
    }

    // If multi-node resize was active, clean up
    if (initialDimensionsRef.current.size > 0) {
      initialDimensionsRef.current.clear();
      // Dispatch resize event to trigger output recalculations for all nodes
      window.dispatchEvent(new Event("resize"));
      return;
    }

    // Single node resize - apply content-based height adjustment
    const measuredHeight = measureContentHeight(
      outputRef.current,
      actualOutputHeight,
    );
    const targetHeight = calculateNodeHeight(
      editorHeight,
      measuredHeight,
      hasOutput,
    );
    updateNodeHeight(targetHeight);

    // Dispatch resize event to trigger output recalculations
    window.dispatchEvent(new Event("resize"));
  });

  return {
    outputRef,
    totalHeight,
    handleResizeStart,
    handleResize,
    handleResizeEnd,
    handleLanguageChange,
    handleConsoleOutputChange,
    triggerResize: resizeTrigger,
    minOutputHeight: LAYOUT.MIN_OUTPUT_HEIGHT,
    footerHeight: LAYOUT.FOOTER_HEIGHT,
  };
}

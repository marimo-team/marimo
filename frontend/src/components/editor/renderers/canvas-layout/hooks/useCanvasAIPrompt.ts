/* Copyright 2024 Marimo. All rights reserved. */

import { useChat } from "@ai-sdk/react";
import { useNodes, useReactFlow } from "@xyflow/react";
import { useAtom, useAtomValue, useStore } from "jotai";
import { useEffect, useRef } from "react";
import useEvent from "react-use-event-hook";
import {
  buildCompletionRequestBody,
  handleToolCall,
} from "@/components/chat/chat-utils";
import { StreamingChunkTransport } from "@/components/editor/ai/transport/chat-transport";
import { toast } from "@/components/ui/use-toast";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import { useCellActions } from "@/core/cells/cells";
import { useRequestClient } from "@/core/network/requests";
import type { AiCompletionRequest } from "@/core/network/types";
import { useRuntimeManager } from "@/core/runtime/config";
import { prettyError } from "@/utils/errors";
import type { CanvasNode } from "../models";
import { NODE_DEFAULTS } from "../models";
import { findOpenSpace } from "../position-utils";
import { canvasAIPromptAtom } from "../state";

/**
 * Hook that provides AI prompt functionality for canvas layout.
 * Handles AI chat integration, cell generation, and viewport animation.
 */
export function useCanvasAIPrompt(language: "python" | "sql" = "python") {
  const store = useStore();
  const [aiPromptState, setAIPromptState] = useAtom(canvasAIPromptAtom);
  const nodes = useNodes<CanvasNode>();
  const { fitView } = useReactFlow();

  const { deleteAllStagedCells, clearStagedCells, onStream, addStagedCell } =
    useStagedCells(store);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool, sendRun } = useRequestClient();

  const stagedAICells = useAtomValue(stagedAICellsAtom);

  const { createNewCell, prepareForRun } = useCellActions();
  const toolContext: ToolNotebookContext = {
    store,
    addStagedCell,
    createNewCell,
    prepareForRun,
    sendRun,
  };

  // Track the position for the next cell
  const nextCellPositionRef = useRef<{ x: number; y: number } | null>(null);

  const { sendMessage, stop, status, addToolResult } = useChat({
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    transport: new StreamingChunkTransport(
      {
        api: runtimeManager.getAiURL("completion").toString(),
        headers: runtimeManager.headers(),
        prepareSendMessagesRequest: async (options) => {
          const completionBody = await buildCompletionRequestBody(
            options.messages,
          );
          const body: AiCompletionRequest = {
            ...options,
            ...completionBody,
            code: "",
            prompt: "", // Don't need prompt since we are using messages
            language: language,
          };

          return {
            body: body,
          };
        },
      },
      (chunk) => {
        onStream(chunk);
      },
    ),
    onToolCall: async ({ toolCall }) => {
      await handleToolCall({
        invokeAiTool,
        addToolResult,
        toolCall: {
          toolName: toolCall.toolName,
          toolCallId: toolCall.toolCallId,
          input: toolCall.input as Record<string, never>,
        },
        toolContext,
      });
    },
    onError: (error) => {
      toast({
        title: "Generate with AI failed",
        description: prettyError(error),
      });
    },
  });

  const isLoading = status === "streaming" || status === "submitted";
  const hasCompletion = stagedAICells.size > 0;
  const multipleCompletions = stagedAICells.size > 1;

  // Calculate position for new cells based on selected nodes
  const calculateNextCellPosition = useEvent(() => {
    const selectedNodes = nodes.filter((node) => node.selected);

    let startX: number;
    let startY: number;

    if (selectedNodes.length === 0) {
      // No selection - use viewport center or a default position
      startX = 100;
      startY = 100;
    } else {
      // Use the last selected node
      const lastSelectedNode = selectedNodes[selectedNodes.length - 1];

      // Start searching to the right of the selected node
      startX = lastSelectedNode.position.x + NODE_DEFAULTS.width + 40;
      startY = lastSelectedNode.position.y;
    }

    // Find open space starting from the calculated position
    return findOpenSpace(startX, startY, nodes);
  });

  // Store position metadata in sessionStorage for canvas.tsx to pick up
  const storePositionMetadata = useEvent(
    (position: { x: number; y: number }) => {
      sessionStorage.setItem(
        "aiCellPositionMeta",
        JSON.stringify({
          position,
        }),
      );
    },
  );

  // Fly viewport to a specific node, properly centered
  const flyToNode = useEvent((nodeId: string) => {
    // Use a small delay to ensure the node has been rendered
    setTimeout(() => {
      fitView({
        nodes: [{ id: nodeId }],
        duration: 400,
        padding: 0.2, // 20% padding around the node
        maxZoom: 1,
      });
    }, 100);
  });

  // Watch for new staged cells and fly to them
  const previousStagedCellsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (stagedAICells.size > previousStagedCellsRef.current.size) {
      // Find the newly added cells
      const currentCellIds = Array.from(stagedAICells.keys());
      const newCellIds = currentCellIds.filter(
        (cellId) => !previousStagedCellsRef.current.has(cellId),
      );

      if (newCellIds.length > 0) {
        // Fly to the LAST newly added cell (most recent one being written to)
        const newCellId = newCellIds[newCellIds.length - 1];
        flyToNode(newCellId);

        // Update position for next cell - find open space near current position
        if (nextCellPositionRef.current) {
          // Find the next open space, searching from the right of the current position
          const nextPos = findOpenSpace(
            nextCellPositionRef.current.x + NODE_DEFAULTS.width / 2,
            nextCellPositionRef.current.y,
            nodes,
          );
          nextCellPositionRef.current = nextPos;
          storePositionMetadata(nextPos);
        }
      }
    }
    previousStagedCellsRef.current = new Set(stagedAICells.keys());
  }, [stagedAICells, nodes, flyToNode, storePositionMetadata]);

  const submit = useEvent(() => {
    if (!isLoading && aiPromptState.prompt.trim()) {
      // Calculate and store position for new cells
      const position = calculateNextCellPosition();
      nextCellPositionRef.current = position;
      storePositionMetadata(position);

      // Delete existing staged cells
      deleteAllStagedCells();

      // Send the message
      sendMessage({ text: aiPromptState.prompt });
    }
  });

  const handleAcceptCompletion = useEvent(() => {
    clearStagedCells();
    setAIPromptState({ isOpen: false, prompt: "" });
    nextCellPositionRef.current = null;
    // Clean up position metadata
    sessionStorage.removeItem("aiCellPositionMeta");
  });

  const handleDeclineCompletion = useEvent(() => {
    deleteAllStagedCells();
    nextCellPositionRef.current = null;
  });

  const handleClose = useEvent(() => {
    deleteAllStagedCells();
    setAIPromptState({ isOpen: false, prompt: "" });
    nextCellPositionRef.current = null;
    // Clean up position metadata
    sessionStorage.removeItem("aiCellPositionMeta");
  });

  const setPrompt = useEvent((prompt: string) => {
    setAIPromptState((prev) => ({ ...prev, prompt }));
  });

  const toggleOpen = useEvent(() => {
    setAIPromptState((prev) => ({ ...prev, isOpen: !prev.isOpen }));
  });

  return {
    aiPromptState,
    setPrompt,
    toggleOpen,
    submit,
    stop,
    isLoading,
    hasCompletion,
    multipleCompletions,
    handleAcceptCompletion,
    handleDeclineCompletion,
    handleClose,
  };
}

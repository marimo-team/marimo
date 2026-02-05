/* Copyright 2026 Marimo. All rights reserved. */

import type { DragDropManager } from "dnd-core";
import type React from "react";
import { createContext, useContext, useState } from "react";
import { DndProvider, useDragDropManager } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";

const DndManagerContext = createContext<DragDropManager | null>(null);

/**
 * Hook to get the shared DragDropManager instance.
 * Must be used within a TreeDndProvider.
 */
export function useTreeDndManager(): DragDropManager | undefined {
  const manager = useContext(DndManagerContext);
  return manager ?? undefined;
}

/**
 * Inner component that extracts and provides the DragDropManager
 */
const DndManagerProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const manager = useDragDropManager();
  return (
    <DndManagerContext.Provider value={manager}>
      {children}
    </DndManagerContext.Provider>
  );
};

/**
 * Wrapper component that provides a shared react-dnd HTML5Backend context.
 * Use this to wrap areas that contain react-arborist Trees to prevent
 * "Cannot have two HTML5 backends at the same time" errors.
 *
 * Pass the manager to Tree via: dndManager={useTreeDndManager()}
 */
export const TreeDndProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  // Use state to store the root element for scoping the backend
  const [rootElement, setRootElement] = useState<HTMLDivElement | null>(null);

  return (
    <div ref={setRootElement} className="contents">
      {rootElement && (
        <DndProvider backend={HTML5Backend} options={{ rootElement }}>
          <DndManagerProvider>{children}</DndManagerProvider>
        </DndProvider>
      )}
    </div>
  );
};

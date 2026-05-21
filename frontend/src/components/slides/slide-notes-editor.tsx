/* Copyright 2026 Marimo. All rights reserved. */

import { StickyNoteIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import type { CellId } from "@/core/cells/ids";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import type { SlidesLayout } from "../editor/renderers/slides-layout/types";

interface SlideNotesEditorProps {
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  cellId: CellId | undefined;
  className?: string;
}

const PERSIST_DELAY_MS = 300;

export const SlideNotesEditor = ({
  layout,
  setLayout,
  cellId,
  className,
}: SlideNotesEditorProps) => {
  const initialValue = cellId
    ? (layout.cells.get(cellId)?.speakerNotes ?? "")
    : "";

  const [draft, setDraft] = useState(initialValue);

  // Tracks whether the user has typed something that hasn't been persisted
  // yet. Used to decide if the textarea is safe to overwrite from props.
  const hasPendingEditRef = useRef(false);

  // The debounced callback takes `(cellId, text)` so a `flush()` replays with
  // the latest args — which means the in-flight text lands on the slide it
  // was typed for, even if `cellId` has since changed.
  const persistImmediate = useEvent((targetCellId: CellId, next: string) => {
    hasPendingEditRef.current = false;
    const existing = layout.cells.get(targetCellId);
    if ((existing?.speakerNotes ?? "") === next) {
      return;
    }
    const newCells = new Map(layout.cells);
    newCells.set(targetCellId, { ...existing, speakerNotes: next });
    setLayout({ ...layout, cells: newCells });
  });

  const persistDebounced = useDebouncedCallback(
    persistImmediate,
    PERSIST_DELAY_MS,
  );

  // Keep the textarea in sync with `layout`:
  // - On slide switch, flush any in-flight edit to the *previous* slide before
  //   adopting the new slide's notes.
  // - On same-slide updates (e.g. future undo/redo or external setLayout
  //   writers), adopt the new value only when the user isn't mid-edit so
  //   pending keystrokes aren't clobbered.
  const prevCellIdRef = useRef(cellId);
  useEffect(() => {
    if (prevCellIdRef.current !== cellId) {
      persistDebounced.flush();
      hasPendingEditRef.current = false;
      setDraft(initialValue);
      prevCellIdRef.current = cellId;
      return;
    }
    if (!hasPendingEditRef.current && initialValue !== draft) {
      setDraft(initialValue);
    }
  }, [cellId, initialValue, draft, persistDebounced]);

  // Flush on unmount so closing the panel / navigating away doesn't lose text.
  useEffect(() => {
    return () => {
      persistDebounced.flush();
    };
  }, [persistDebounced]);

  const handleChange = (next: string) => {
    setDraft(next);
    if (cellId) {
      hasPendingEditRef.current = true;
      persistDebounced(cellId, next);
    }
  };

  return (
    <section
      className={cn(
        "h-full min-h-0 flex flex-col bg-muted/40 dark:bg-muted/20 border-t",
        className,
      )}
      aria-label="Speaker notes"
      // Keep keystrokes inside the textarea from advancing the reveal.js deck.
      onKeyDown={(e) => e.stopPropagation()}
    >
      <header className="flex items-center gap-1.5 px-3 h-8 shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <StickyNoteIcon className="h-3.5 w-3.5" />
        <span>Speaker notes</span>
      </header>
      <div className="flex-1 min-h-0 p-2">
        {cellId ? (
          <textarea
            value={draft}
            onChange={(event) => handleChange(event.target.value)}
            onClick={Events.stopPropagation()}
            placeholder="Add notes for this slide. Visible to you in speaker view (press S during presentation)."
            className={cn(
              "h-full w-full resize-none rounded-sm border border-input/25 bg-background",
              "px-3 py-2 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground",
              "ring-offset-background focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-accent",
            )}
            aria-label="Speaker notes for the current slide"
          />
        ) : (
          <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
            Select a slide to add notes.
          </div>
        )}
      </div>
    </section>
  );
};

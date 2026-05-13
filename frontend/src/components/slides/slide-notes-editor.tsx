/* Copyright 2026 Marimo. All rights reserved. */

import { StickyNoteIcon } from "lucide-react";
import { useCallback } from "react";
import type { CellId } from "@/core/cells/ids";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import type { SlidesLayout } from "../editor/renderers/slides-layout/types";

interface SlideNotesEditorProps {
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  cellId: CellId | undefined;
  className?: string;
}

export const SlideNotesEditor = ({
  layout,
  setLayout,
  cellId,
  className,
}: SlideNotesEditorProps) => {
  const initialValue = cellId
    ? (layout.cells.get(cellId)?.speakerNotes ?? "")
    : "";

  const handlePersist = useCallback(
    (next: string) => {
      if (!cellId) {
        return;
      }
      const existing = layout.cells.get(cellId);
      const previous = existing?.speakerNotes ?? "";
      if (previous === next) {
        return;
      }
      const newCells = new Map(layout.cells);
      newCells.set(cellId, { ...existing, speakerNotes: next });
      setLayout({ ...layout, cells: newCells });
    },
    [cellId, layout, setLayout],
  );

  const { value, onChange } = useDebounceControlledState<string>({
    initialValue,
    delay: 300,
    onChange: handlePersist,
    disabled: cellId == null,
  });

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
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onClick={Events.stopPropagation()}
            placeholder="Add notes for this slide. Visible to you in speaker view (press S during presentation)."
            className={cn(
              "h-full w-full resize-none rounded-sm border border-input bg-background",
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

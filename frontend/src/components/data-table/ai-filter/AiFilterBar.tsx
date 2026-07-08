/* Copyright 2026 Marimo. All rights reserved. */

import { completionStatus } from "@codemirror/autocomplete";
import type { FilterAST } from "better-filter-bar";
import { FilterBar, parseQuery, useFilterBar } from "better-filter-bar/react";
import { SparklesIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { Spinner } from "../../icons/spinner";
import { Button } from "../../ui/button";
import "./ai-filter.css";
import type { AiFilterState } from "./useAiFilter";

interface AiFilterBarProps {
  ai: AiFilterState;
}

/**
 * The editable FQL editor shown in place of the search input while AI-filter
 * mode is active. Edits apply on submit (Enter), not on every keystroke.
 */
export const AiFilterBar = ({ ai }: AiFilterBarProps) => {
  const { viewRef, getValue } = useFilterBar(ai.schema);
  const [dirty, setDirty] = useState(false);

  // A fresh generation applies its own query, so it starts clean.
  useEffect(() => {
    setDirty(false);
  }, [ai.generationId]);

  const handleChange = useEvent((_ast: FilterAST, raw: string) => {
    setDirty(raw.trim() !== ai.appliedRaw.trim());
  });

  const apply = useEvent((ast: FilterAST, raw: string) => {
    ai.applyFromEditor(ast, raw);
    setDirty(false);
  });

  // Submit the current editor contents (used by the button and by Enter).
  const submitCurrent = useEvent(() => {
    const raw = getValue();
    apply(parseQuery(raw, ai.schema), raw);
  });

  // The packaged editor's Enter binding inserts a space instead of submitting.
  // Capture Enter to run the query — unless the autocomplete popup is open, in
  // which case let CodeMirror accept the highlighted completion.
  const wrapperRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Enter" || event.shiftKey) {
        return;
      }
      const view = viewRef.current;
      if (view && completionStatus(view.state) !== null) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      submitCurrent();
    };
    el.addEventListener("keydown", onKeyDown, { capture: true });
    return () =>
      el.removeEventListener("keydown", onKeyDown, { capture: true });
  }, [submitCurrent, viewRef]);

  return (
    <div className="flex flex-1 items-center gap-1 px-2 min-w-0">
      <SparklesIcon className="w-4 h-4 text-primary shrink-0" />
      <div ref={wrapperRef} className="flex-1 min-w-0">
        <FilterBar
          // Re-key on each generation so the editor re-seeds from `rawQuery`.
          key={ai.generationId}
          viewRef={viewRef}
          schema={ai.schema}
          initialValue={ai.rawQuery}
          placeholder={ai.isGenerating ? "Generating filter…" : "Filter query…"}
          readOnly={ai.isGenerating}
          onChange={handleChange}
          onSubmit={apply}
          className="marimo-ai-filter-bar w-full"
        />
      </div>
      {ai.isGenerating && <Spinner size="small" />}
      {!ai.isGenerating && dirty && (
        <Button
          variant="outline"
          size="xs"
          onClick={submitCurrent}
          className="h-6 px-2 text-xs text-muted-foreground whitespace-nowrap shrink-0"
        >
          Press ↵ to search
        </Button>
      )}
      {ai.error && (
        <span
          className="text-xs text-destructive line-clamp-1 shrink-0 max-w-64"
          title={ai.error}
        >
          {ai.error}
        </span>
      )}
      <Button
        variant="text"
        size="xs"
        className="h-5 w-5 p-0 shrink-0"
        onClick={ai.clear}
        aria-label="Exit AI filter"
      >
        <XIcon className="w-3 h-3 text-muted-foreground" />
      </Button>
    </div>
  );
};

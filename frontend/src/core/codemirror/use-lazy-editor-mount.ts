/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { useEffect, useRef, useState, type RefObject } from "react";
import useEvent from "react-use-event-hook";
import { createSharedIntersectionObserver } from "@/utils/shared-intersection-observer";
import { editorMountScheduler } from "./editor-mount-scheduler";

const observeEditor = createSharedIntersectionObserver({
  rootMargin: "300px 0px",
  threshold: 0,
});

/**
 * Owns registration, viewport eligibility, and the editor's entire lifetime.
 * `build` must assign `editorViewRef`; construct inside it so a deferred
 * editor starts from the latest code and configuration.
 */
export function useLazyEditorMount({
  cellId,
  editorViewRef,
  build,
  hidden,
}: {
  cellId: string;
  editorViewRef: RefObject<EditorView | null>;
  build: () => void;
  hidden: boolean;
}) {
  const elementRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const buildLatest = useEvent(() => {
    build();
    setMounted(true);
  });

  useEffect(() => {
    setMounted(false);
    const cancel = editorMountScheduler.register(cellId, buildLatest);
    return () => {
      cancel();
      editorViewRef.current?.destroy();
      editorViewRef.current = null;
    };
  }, [cellId, buildLatest, editorViewRef]);

  const awaitsVisibility = !mounted && !hidden;
  useEffect(() => {
    const element = elementRef.current;
    if (!awaitsVisibility || !element) {
      return;
    }
    const release = observeEditor(element, (visible) => {
      if (visible) {
        editorMountScheduler.prioritize(cellId);
      } else {
        editorMountScheduler.deprioritize(cellId);
      }
    });
    return () => {
      release();
      editorMountScheduler.deprioritize(cellId);
    };
  }, [cellId, awaitsVisibility]);

  const promote = useEvent(() => editorMountScheduler.promote(cellId));
  return { elementRef, mounted, promote };
}

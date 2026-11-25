/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import useEvent from "react-use-event-hook";
import { useSharedIntersectionObserver } from "@/hooks/useSharedIntersectionObserver";
import { createSharedIntersectionObserver } from "@/utils/shared-intersection-observer";
import { editorMountScheduler } from "./editor-mount-scheduler";

const observeEditor = createSharedIntersectionObserver({
  rootMargin: "300px 0px",
  threshold: 0,
});

/** Owns registration, viewport eligibility, and the editor's entire lifetime. */
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
    if (!editorViewRef.current) {
      build();
    }
    setMounted(true);
  });

  useEffect(() => {
    setMounted(false);
    const cancel = editorMountScheduler.request(cellId, buildLatest, true);
    return () => {
      cancel();
      editorViewRef.current?.destroy();
      editorViewRef.current = null;
    };
  }, [cellId, buildLatest, editorViewRef]);

  const onVisibilityChange = useCallback(
    (visible: boolean) => {
      if (visible) {
        editorMountScheduler.prioritize(cellId);
      } else {
        editorMountScheduler.deprioritize(cellId);
      }
    },
    [cellId],
  );
  useSharedIntersectionObserver(
    elementRef,
    observeEditor,
    onVisibilityChange,
    !mounted && !hidden,
  );

  const promote = useEvent(() => editorMountScheduler.promote(cellId));
  return { elementRef, mounted, promote };
}

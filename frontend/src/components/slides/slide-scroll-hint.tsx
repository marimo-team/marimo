/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronDownIcon } from "lucide-react";
import {
  type ReactNode,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";
import { cn } from "@/utils/cn";

/** Pixels of scroll before the hint is considered dismissed. */
const TOP_THRESHOLD_PX = 8;
/** Ignore sub-pixel overflow from rounding / borders. */
const OVERFLOW_TOLERANCE_PX = 1;

/**
 * Whether a scroll container should show a "more content below" affordance.
 * Visible only when content overflows and the viewport is still near the top.
 */
export function shouldShowScrollHint(options: {
  scrollHeight: number;
  clientHeight: number;
  scrollTop: number;
}): boolean {
  const { scrollHeight, clientHeight, scrollTop } = options;
  const overflowing = scrollHeight > clientHeight + OVERFLOW_TOLERANCE_PX;
  const atTop = scrollTop <= TOP_THRESHOLD_PX;
  return overflowing && atTop;
}

/**
 * Tracks whether a scroll container is overflowing at the top, so we can
 * surface a scroll affordance.
 */
function useScrollHint(
  scrollRef: RefObject<HTMLElement | null>,
  contentRef: RefObject<HTMLElement | null>,
): boolean {
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    const content = contentRef.current;
    if (!el || !content) {
      return;
    }

    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        setShowHint(
          shouldShowScrollHint({
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            scrollTop: el.scrollTop,
          }),
        );
      });
    };

    update();

    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(el);
    resizeObserver.observe(content);

    el.addEventListener("scroll", update, { passive: true });

    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      el.removeEventListener("scroll", update);
    };
  }, [scrollRef, contentRef]);

  return showHint;
}

const ScrollHintOverlay = ({ className }: { className?: string }) => {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-x-0 bottom-0 z-10 flex flex-col items-center",
        "animate-in fade-in-0 duration-200",
        className,
      )}
      data-testid="slide-scroll-hint"
      aria-hidden={true}
    >
      <div className="h-16 w-full bg-linear-to-t from-background via-background/80 to-transparent" />
      <div className="absolute bottom-3 flex items-center gap-1 rounded-full border border-border/60 bg-background/90 px-2.5 py-1 text-xs text-muted-foreground shadow-sm backdrop-blur-sm">
        <ChevronDownIcon className="h-3.5 w-3.5" />
        <span>Scroll for more</span>
      </div>
    </div>
  );
};

/**
 * Full-height scroll container for a slide. Shows a dismissible "Scroll for
 * more" cue when content overflows the frame (easy to miss in fullscreen when
 * OS overlay scrollbars are hidden).
 */
export const SlideScrollContainer = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const showHint = useScrollHint(scrollRef, contentRef);

  return (
    <div className={cn("relative h-full w-full", className)}>
      <div
        ref={scrollRef}
        className="h-full w-full overflow-auto flex"
        data-testid="slide-scroll-container"
      >
        <div ref={contentRef} className="flex w-full">
          {children}
        </div>
      </div>
      {showHint && <ScrollHintOverlay />}
    </div>
  );
};

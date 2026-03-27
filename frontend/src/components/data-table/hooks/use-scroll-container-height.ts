/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useLayoutEffect, useRef } from "react";
import {
  DEFAULT_VIRTUAL_ROWS,
  TABLE_HEADER_HEIGHT_PX,
  TABLE_ROW_HEIGHT_PX,
} from "../types";

/**
 * Manages the scroll container's max-height for the data table.
 *
 * The <Table> UI component wraps <table> in a div with overflow-auto.
 * We derive the scroll boundary from this wrapper (tableRef.parentElement)
 * to keep sticky headers working without coupling base components to
 * data-table specifics.
 *
 * Three modes:
 * - Explicit `maxHeight`: applied directly.
 * - Virtualize (no explicit maxHeight): observed via ResizeObserver on <thead>
 *   so the container reacts to header size changes (charts loading, toggles).
 * - Neither: max-height is removed so the table grows freely.
 */
export function useScrollContainerHeight({
  maxHeight,
  virtualize,
}: {
  maxHeight?: number;
  virtualize: boolean;
}) {
  const tableRef = useRef<HTMLTableElement | null>(null);

  // Handle explicit maxHeight and non-virtualize cases synchronously
  // before paint to avoid flickering.
  useLayoutEffect(() => {
    if (!tableRef.current) {
      return;
    }
    const wrapper = tableRef.current.parentElement as HTMLDivElement | null;
    if (!wrapper) {
      return;
    }
    if (maxHeight) {
      wrapper.style.maxHeight = `${maxHeight}px`;
      if (!wrapper.style.overflow) {
        wrapper.style.overflow = "auto";
      }
    } else if (!virtualize) {
      wrapper.style.removeProperty("max-height");
    }
    // When virtualizing without an explicit maxHeight, the ResizeObserver
    // below handles setting maxHeight reactively based on actual header size.
  }, [maxHeight, virtualize]);

  // When virtualizing without an explicit maxHeight, observe the <thead> for
  // size changes (column summaries, charts loading async, header toggle) and
  // recompute the scroll container height accordingly.
  useEffect(() => {
    if (!virtualize || maxHeight) {
      return;
    }
    const table = tableRef.current;
    if (!table) {
      return;
    }
    const wrapper = table.parentElement as HTMLDivElement | null;
    const thead = table.querySelector("thead");
    if (!wrapper || !thead) {
      return;
    }
    const updateMaxHeight = () => {
      const headerHeight =
        thead.getBoundingClientRect().height || TABLE_HEADER_HEIGHT_PX;
      const firstRow = table.querySelector("tbody tr");
      const rowHeight =
        firstRow?.getBoundingClientRect().height || TABLE_ROW_HEIGHT_PX;
      wrapper.style.maxHeight = `${DEFAULT_VIRTUAL_ROWS * rowHeight + headerHeight}px`;
    };

    // Set initial height
    updateMaxHeight();

    const observer = new ResizeObserver(updateMaxHeight);
    observer.observe(thead);
    return () => observer.disconnect();
  }, [virtualize, maxHeight]);

  return tableRef;
}

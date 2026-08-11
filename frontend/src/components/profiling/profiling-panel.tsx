/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue, useSetAtom } from "jotai";
import { GaugeIcon } from "lucide-react";
import React, { useEffect, useRef } from "react";
import { ClearButton } from "@/components/buttons/clear-button";
import { PanelEmptyState } from "@/components/editor/chrome/panels/empty-state";
import {
  atomSubscriberCountAtom,
  componentRenderCountAtom,
  domNodeCountAtom,
  editorViewCountAtom,
  profilerEventsAtom,
  profilingEnabledAtom,
  resetProfilingAtom,
  wsMessageCountAtom,
  wsMessageRateAtom,
} from "@/core/profiling/atoms";
import { store } from "@/core/state/jotai";

const POLL_INTERVAL_MS = 1000;

export const ProfilingPanel: React.FC = () => {
  const profilingEnabled = useAtomValue(profilingEnabledAtom);
  const renderCounts = useAtomValue(componentRenderCountAtom);
  const subscriberCounts = useAtomValue(atomSubscriberCountAtom);
  const editorViewCount = useAtomValue(editorViewCountAtom);
  const domNodeCount = useAtomValue(domNodeCountAtom);
  const wsMessageRate = useAtomValue(wsMessageRateAtom);
  const profilerEvents = useAtomValue(profilerEventsAtom);
  const resetProfiling = useSetAtom(resetProfilingAtom);
  const lastMessageCountRef = useRef(0);

  // Poll DOM size and WS message rate once per second while the panel is open.
  useEffect(() => {
    if (!profilingEnabled) {
      return;
    }
    const interval = setInterval(() => {
      store.set(domNodeCountAtom, document.querySelectorAll("*").length);
      const count = store.get(wsMessageCountAtom);
      store.set(wsMessageRateAtom, count - lastMessageCountRef.current);
      lastMessageCountRef.current = count;
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [profilingEnabled]);

  if (!profilingEnabled) {
    return (
      <PanelEmptyState
        title="Profiling disabled"
        description={
          <span>
            Add <code>?profile=1</code> to the URL and reload to start
            collecting metrics.
          </span>
        }
        icon={<GaugeIcon />}
      />
    );
  }

  const sortedComponents = Object.entries(renderCounts).toSorted(
    (a, b) => b[1] - a[1],
  );
  const totalRenders = sortedComponents.reduce(
    (sum, [, count]) => sum + count,
    0,
  );
  const sortedAtoms = Object.entries(subscriberCounts).toSorted(
    (a, b) => b[1] - a[1],
  );

  const profilerRollup = new Map<
    string,
    { count: number; total: number; max: number }
  >();
  for (const event of profilerEvents) {
    const entry = profilerRollup.get(event.id) ?? {
      count: 0,
      total: 0,
      max: 0,
    };
    entry.count += 1;
    entry.total += event.actualDuration;
    entry.max = Math.max(entry.max, event.actualDuration);
    profilerRollup.set(event.id, entry);
  }
  const sortedProfiler = [...profilerRollup.entries()].toSorted(
    (a, b) => b[1].total - a[1].total,
  );

  const exportJson = () => {
    void navigator.clipboard.writeText(
      JSON.stringify(
        {
          componentRenderCounts: renderCounts,
          atomSubscriberCounts: subscriberCounts,
          editorViewCount,
          wsMessageRate,
          domNodeCount,
          profilerEvents,
        },
        null,
        2,
      ),
    );
  };

  return (
    <div className="py-1 px-2 overflow-y-scroll h-full text-xs">
      <div className="flex flex-row justify-start gap-3 mb-2">
        <ClearButton
          dataTestId="reset-profiling-button"
          onClick={resetProfiling}
        />
        <button
          type="button"
          className="font-semibold text-accent-foreground"
          onClick={exportJson}
          data-testid="export-profiling-button"
        >
          Export JSON
        </button>
      </div>

      <div className="flex flex-row gap-6 mb-3">
        <span>Total renders: {totalRenders}</span>
        <span>Editor views: {editorViewCount}</span>
        <span>WS msgs/sec: {wsMessageRate}</span>
        <span>DOM nodes: {domNodeCount}</span>
      </div>

      <div className="flex flex-col gap-2">
        <div className="font-semibold">Top components by render count</div>
        {sortedComponents.length === 0 ? (
          <div className="opacity-70">No renders recorded yet.</div>
        ) : (
          sortedComponents.map(([name, count]) => (
            <div key={name} className="flex flex-row justify-between py-0.5">
              <span>{name}</span>
              <span>{count}</span>
            </div>
          ))
        )}

        <div className="font-semibold mt-3">Atom subscriber activity</div>
        {sortedAtoms.length === 0 ? (
          <div className="opacity-70">
            None recorded. Populated by the incremental-atom work (Track B.2).
          </div>
        ) : (
          sortedAtoms.map(([name, count]) => (
            <div key={name} className="flex flex-row justify-between py-0.5">
              <span>{name}</span>
              <span>{count}</span>
            </div>
          ))
        )}

        <div className="font-semibold mt-3">Slowest renders</div>
        {sortedProfiler.length === 0 ? (
          <div className="opacity-70">
            Render durations require a development build (or a
            react-dom/profiling alias).
          </div>
        ) : (
          sortedProfiler.map(([id, { count, total, max }]) => (
            <div key={id} className="flex flex-row justify-between py-0.5">
              <span>{id}</span>
              <span>
                {count} renders · {total.toFixed(1)} ms total · avg{" "}
                {(total / count).toFixed(1)} ms · max {max.toFixed(1)} ms
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

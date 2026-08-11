/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";

const initialProfilingEnabled =
  typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).has("profile");

export const profilingEnabledAtom = atom(initialProfilingEnabled);

export const componentRenderCountAtom = atom<Record<string, number>>({});

export const atomSubscriberCountAtom = atom<Record<string, number>>({});

export const editorViewCountAtom = atom(0);
export const wsMessageCountAtom = atom(0);
export const wsMessageRateAtom = atom(0);
export const domNodeCountAtom = atom(0);

export interface ProfilerEvent {
  id: string;
  phase: "mount" | "update" | "nested-update";
  actualDuration: number;
  baseDuration: number;
  timestamp: number;
}

export const MAX_PROFILER_EVENTS = 100;

// Capped ring buffer — trimmed at write time so the atom stays bounded
export const profilerEventsAtom = atom<ProfilerEvent[]>([]);

export const resetProfilingAtom = atom(null, (_get, set) => {
  set(componentRenderCountAtom, {});
  set(atomSubscriberCountAtom, {});
  set(editorViewCountAtom, 0);
  set(wsMessageCountAtom, 0);
  set(wsMessageRateAtom, 0);
  set(domNodeCountAtom, 0);
  set(profilerEventsAtom, []);
});

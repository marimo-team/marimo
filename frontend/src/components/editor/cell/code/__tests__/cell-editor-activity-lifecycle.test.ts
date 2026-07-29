/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Simulates React Activity's effect teardown when mode switches to "hidden":
 * all useEffect cleanups run, then on "visible" effects re-run. Component state
 * and DOM are preserved — only effects cycle.
 *
 * Registration order matches cell-editor.tsx: mount effect runs before destroy
 * effect setup. With async editor creation (editorMountScheduler), destroy
 * captures null initially; with sync creation it captures the live editor.
 */
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import { Functions } from "@/utils/functions";

interface EffectRegistration {
  cleanup: () => void;
}

function createActivitySimulator() {
  const effects: EffectRegistration[] = [];

  return {
    /** Register effects in order — each setup runs synchronously, like React. */
    useEffect(setup: () => (() => void) | undefined) {
      const cleanup = setup() ?? Functions.NOOP;
      effects.push({ cleanup });
    },
    hide() {
      for (const effect of effects) {
        effect.cleanup();
      }
    },
    show() {
      for (const effect of effects) {
        effect.cleanup();
      }
      effects.length = 0;
    },
  };
}

function createEditor(doc = "hello") {
  return new EditorView({
    state: EditorState.create({ doc }),
  });
}

interface RegisterCellEditorEffectsOptions {
  activity: ReturnType<typeof createActivitySimulator>;
  editorViewRef: { current: EditorView | null };
  destroyPattern: "old" | "pr";
  onDestroy?: () => void;
  /** When true, editor creation is deferred like editorMountScheduler.request */
  asyncMount?: boolean;
}

function registerCellEditorEffects({
  activity,
  editorViewRef,
  destroyPattern,
  onDestroy,
  asyncMount = false,
}: RegisterCellEditorEffectsOptions) {
  activity.useEffect(() => {
    if (editorViewRef.current !== null) {
      return;
    }
    let cancelled = false;
    const mount = () => {
      if (!cancelled && editorViewRef.current === null) {
        editorViewRef.current = createEditor();
      }
    };
    if (asyncMount) {
      const id = setTimeout(mount, 0);
      return () => {
        cancelled = true;
        clearTimeout(id);
      };
    }
    mount();
    return () => {
      cancelled = true;
    };
  });

  if (destroyPattern === "old") {
    activity.useEffect(() => {
      const ev = editorViewRef.current;
      return () => {
        if (ev) {
          ev.destroy();
          onDestroy?.();
        }
      };
    });
  } else {
    activity.useEffect(() => {
      return () => {
        if (editorViewRef.current) {
          editorViewRef.current.destroy();
          onDestroy?.();
        }
        editorViewRef.current = null;
      };
    });
  }
}

describe("CellEditor Activity lifecycle (simulated)", () => {
  it("old destroy pattern (sync mount): first hide/show leaves stale ref", () => {
    const editorViewRef = { current: null as EditorView | null };
    let destroyCount = 0;
    const activity = createActivitySimulator();

    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "old",
      onDestroy: () => {
        destroyCount++;
      },
    });
    const liveEditor = editorViewRef.current;
    expect(liveEditor).not.toBeNull();

    activity.hide();
    expect(destroyCount).toBeGreaterThan(0);
    expect(editorViewRef.current).toBe(liveEditor);

    activity.show();
    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "old",
    });
    expect(editorViewRef.current).toBe(liveEditor);
  });

  it("old destroy pattern (async mount): first hide/show preserves editor", async () => {
    const editorViewRef = { current: null as EditorView | null };
    let destroyCount = 0;
    const activity = createActivitySimulator();

    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "old",
      onDestroy: () => {
        destroyCount++;
      },
      asyncMount: true,
    });
    await new Promise((r) => setTimeout(r, 0));
    const liveEditor = editorViewRef.current;
    expect(liveEditor).not.toBeNull();

    // Destroy effect captured null at setup (editor created async after effects)
    activity.hide();
    expect(destroyCount).toBe(0);
    expect(editorViewRef.current).toBe(liveEditor);

    activity.show();
    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "old",
      asyncMount: true,
    });
    await new Promise((r) => setTimeout(r, 0));
    expect(editorViewRef.current).toBe(liveEditor);
  });

  it("PR destroy pattern (async mount): recreates on first hide/show", async () => {
    const editorViewRef = { current: null as EditorView | null };
    const activity = createActivitySimulator();

    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "pr",
      asyncMount: true,
    });
    await new Promise((r) => setTimeout(r, 0));
    const firstEditor = editorViewRef.current;

    activity.hide();
    expect(editorViewRef.current).toBeNull();

    activity.show();
    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "pr",
      asyncMount: true,
    });
    await new Promise((r) => setTimeout(r, 0));
    expect(editorViewRef.current).not.toBeNull();
    expect(editorViewRef.current).not.toBe(firstEditor);
  });

  it("PR destroy pattern: nulls ref on hide so mount recreates on show", () => {
    const editorViewRef = { current: null as EditorView | null };
    const activity = createActivitySimulator();

    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "pr",
    });
    const firstEditor = editorViewRef.current;

    activity.hide();
    expect(editorViewRef.current).toBeNull();

    activity.show();
    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "pr",
    });
    expect(editorViewRef.current).not.toBeNull();
    expect(editorViewRef.current).not.toBe(firstEditor);
  });

  it("PR destroy pattern: stable across repeated hide/show cycles", () => {
    const editorViewRef = { current: null as EditorView | null };
    const activity = createActivitySimulator();

    for (let i = 0; i < 3; i++) {
      registerCellEditorEffects({
        activity,
        editorViewRef,
        destroyPattern: "pr",
      });
      expect(editorViewRef.current).not.toBeNull();

      activity.hide();
      expect(editorViewRef.current).toBeNull();

      activity.show();
    }

    registerCellEditorEffects({
      activity,
      editorViewRef,
      destroyPattern: "pr",
    });
    expect(editorViewRef.current).not.toBeNull();
  });
});

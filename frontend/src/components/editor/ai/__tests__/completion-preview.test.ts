/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  captureSessionBaseline,
  codeToRestoreOnReject,
  originalCodeForMerge,
  shouldRestoreBeforeResubmit,
} from "../completion-preview";

describe("captureSessionBaseline", () => {
  it("returns currentCode when no baseline exists yet", () => {
    expect(captureSessionBaseline(null, "x = 1")).toBe("x = 1");
  });

  it("keeps the existing baseline on later calls", () => {
    expect(captureSessionBaseline("x = 1", "x = 2")).toBe("x = 1");
  });
});

describe("codeToRestoreOnReject", () => {
  it("returns baseline when previewed", () => {
    expect(
      codeToRestoreOnReject({ hasPreviewed: true, baseline: "orig" }),
    ).toBe("orig");
  });

  it("returns null when not previewed", () => {
    expect(
      codeToRestoreOnReject({ hasPreviewed: false, baseline: "orig" }),
    ).toBeNull();
  });

  it("returns null when previewed but baseline missing", () => {
    expect(
      codeToRestoreOnReject({ hasPreviewed: true, baseline: null }),
    ).toBeNull();
  });
});

describe("codeToRestoreOnReject used as the [enabled]-effect safety net", () => {
  // The ai-completion-editor's `[enabled]` effect reuses codeToRestoreOnReject
  // to decide whether to restore the baseline when the AI panel closes
  // without going through handleDeclineCompletion (hotkey toggle, toolbar
  // toggle, or switching AI to another cell).
  it("restores baseline when panel closes after a preview run", () => {
    const restore = codeToRestoreOnReject({
      hasPreviewed: true,
      baseline: "original code",
    });
    expect(restore).toBe("original code");
  });

  it("does nothing when panel closes without ever previewing", () => {
    const restore = codeToRestoreOnReject({
      hasPreviewed: false,
      baseline: "original code",
    });
    expect(restore).toBeNull();
  });

  it("does nothing when accept already cleared the preview flags first", () => {
    // handleAcceptCompletion clears hasPreviewedRef/sessionBaselineRef before
    // calling acceptChange, so even if the effect races in afterwards it
    // must not undo the accept.
    const restore = codeToRestoreOnReject({
      hasPreviewed: false,
      baseline: null,
    });
    expect(restore).toBeNull();
  });
});

describe("shouldRestoreBeforeResubmit", () => {
  it("is true only after preview", () => {
    expect(shouldRestoreBeforeResubmit(true)).toBe(true);
    expect(shouldRestoreBeforeResubmit(false)).toBe(false);
  });
});

describe("originalCodeForMerge", () => {
  it("uses live currentCode before preview", () => {
    expect(
      originalCodeForMerge({
        hasPreviewed: false,
        baseline: "orig",
        currentCode: "live",
      }),
    ).toBe("live");
  });

  it("uses baseline after preview when baseline is set", () => {
    expect(
      originalCodeForMerge({
        hasPreviewed: true,
        baseline: "orig",
        currentCode: "suggested",
      }),
    ).toBe("orig");
  });

  it("falls back to currentCode after preview if baseline missing", () => {
    expect(
      originalCodeForMerge({
        hasPreviewed: true,
        baseline: null,
        currentCode: "suggested",
      }),
    ).toBe("suggested");
  });
});

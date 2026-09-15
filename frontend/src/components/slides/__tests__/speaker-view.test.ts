/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  createSpeakerViewUrl,
  isSpeakerViewReceiver,
  supportsSpeakerView,
} from "../speaker-view";

describe("speaker view policy", () => {
  it("builds a receiver base URL independently of the active Reveal hash", () => {
    expect(
      createSpeakerViewUrl("https://example.test/deck?theme=dark#/2/1"),
    ).toBe("https://example.test/deck?theme=dark&kiosk=true&show-chrome=false");
  });

  it("recognizes kiosk receiver frames", () => {
    expect(isSpeakerViewReceiver(true, "?kiosk=true&receiver")).toBe(true);
    expect(isSpeakerViewReceiver(false, "?receiver")).toBe(false);
  });

  it("keeps speaker view on shared and static runtimes", () => {
    expect(supportsSpeakerView("remote")).toBe(true);
    expect(supportsSpeakerView("static")).toBe(true);
    expect(supportsSpeakerView("wasm")).toBe(false);
  });
});

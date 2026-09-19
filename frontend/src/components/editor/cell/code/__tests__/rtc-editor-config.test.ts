/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import { composeRtcEditorConfig } from "../cell-editor";

describe("composeRtcEditorConfig", () => {
  it("does not accumulate RTC extensions across reconfigurations", () => {
    const baseExtension = EditorState.readOnly.of(false);
    const baseExtensions = [baseExtension];
    const firstRtc = {
      code: "first RTC code",
      extension: EditorState.tabSize.of(2),
    };
    const secondRtc = {
      code: "second RTC code",
      extension: EditorState.tabSize.of(4),
    };

    const firstConfig = composeRtcEditorConfig(
      "local code",
      baseExtensions,
      firstRtc,
    );
    const secondConfig = composeRtcEditorConfig(
      "local code",
      baseExtensions,
      secondRtc,
    );

    expect(baseExtensions).toEqual([baseExtension]);
    expect(firstConfig).toEqual({
      code: firstRtc.code,
      extensions: [baseExtension, firstRtc.extension],
    });
    expect(secondConfig).toEqual({
      code: secondRtc.code,
      extensions: [baseExtension, secondRtc.extension],
    });
  });

  it("reuses the base configuration when RTC is disabled", () => {
    const extensions = [EditorState.readOnly.of(false)];

    const config = composeRtcEditorConfig("local code", extensions, undefined);

    expect(config).toEqual({ code: "local code", extensions });
    expect(config.extensions).toBe(extensions);
  });
});

/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildMediaSource, FileContentRenderer } from "../renderers";

vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: ({
    value,
    language,
    readOnly,
    onChange,
  }: {
    value?: string;
    language?: string;
    readOnly?: boolean;
    onChange?: (value: string) => void;
  }) => (
    <textarea
      data-testid="code-editor"
      data-language={language}
      value={value}
      readOnly={readOnly}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

describe("buildMediaSource", () => {
  it("returns base64 source for binary media", () => {
    expect(
      buildMediaSource({
        contents: "aGVsbG8=",
        mimeType: "image/png",
        isBase64: true,
      }),
    ).toEqual({
      base64: "aGVsbG8=",
      mime: "image/png",
    });
  });

  it("returns UTF-8 data URL for text-based media", () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>';
    expect(
      buildMediaSource({
        contents: svg,
        mimeType: "image/svg+xml",
        isBase64: false,
      }),
    ).toEqual({
      url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
    });
  });
});

describe("FileContentRenderer", () => {
  it("renders editable TOML with syntax highlighting", () => {
    const onChange = vi.fn();
    render(
      <FileContentRenderer
        mimeType="application/toml"
        contents={'name = "demo"'}
        readOnly={false}
        onChange={onChange}
      />,
    );

    const editor = screen.getByTestId<HTMLTextAreaElement>("code-editor");
    expect(editor).toHaveAttribute("data-language", "toml");
    expect(editor).not.toHaveAttribute("readonly");

    fireEvent.change(editor, { target: { value: 'name = "updated"' } });
    expect(onChange).toHaveBeenCalledWith('name = "updated"');
  });

  it.each(["application/toml", "application/x-toml", "text/x-toml"])(
    "renders %s as read-only TOML by default",
    (mimeType) => {
      render(
        <FileContentRenderer mimeType={mimeType} contents={'name = "demo"'} />,
      );

      const editor = screen.getByTestId<HTMLTextAreaElement>("code-editor");
      expect(editor).toHaveAttribute("data-language", "toml");
      expect(editor).toHaveAttribute("readonly");
    },
  );

  it.each([
    "application/octet-stream",
    "text/plain",
    "text/plain; charset=utf-8",
  ])("uses the filename when a provider returns %s", (mimeType) => {
    render(
      <FileContentRenderer
        mimeType={mimeType}
        filename="pyproject.TOML"
        contents={'name = "demo"'}
      />,
    );

    expect(screen.getByTestId("code-editor")).toHaveAttribute(
      "data-language",
      "toml",
    );
  });
});

/* Copyright 2024 Marimo. All rights reserved. */
import { AnsiUp } from "ansi_up";
import { describe, expect, test } from "vitest";

const ansiUp = new AnsiUp();

describe("ansi", () => {
  test("basic", () => {
    const text = "string";
    const value = ansiUp.ansi_to_html(text);
    expect(value).toMatchInlineSnapshot(`"string"`);
  });

  test("with ansi", () => {
    const text = "'\u001B[30mblack\u001B[37mwhite'";
    const value = ansiUp.ansi_to_html(text);
    expect(value).toMatchInlineSnapshot(
      `"&#x27;<span style="color:rgb(0,0,0)">black</span><span style="color:rgb(255,255,255)">white&#x27;</span>"`,
    );
  });

  test("with html", () => {
    // HTML gets escaped
    const text = "<b>string</b>";
    const value = ansiUp.ansi_to_html(text);
    expect(value).toMatchInlineSnapshot(
      `"<span style="color:rgb(255,255,255)">&lt;b&gt;string&lt;/b&gt;</span>"`,
    );
  });

  test("with ansi and html", () => {
    // HTML gets escaped
    const text = "'\u001B[1m<b>string\u001B[0m</b>'";
    const value = ansiUp.ansi_to_html(text);
    expect(value).toMatchInlineSnapshot(
      `"<span style="color:rgb(255,255,255)">&#x27;</span><span style="font-weight:bold;color:rgb(255,255,255)">&lt;b&gt;string</span>&lt;/b&gt;&#x27;"`,
    );
  });
});

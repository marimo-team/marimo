/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { ansiToPlainText, parseHtmlContent } from "../dom";

describe("parseHtmlContent", () => {
  test("strips HTML tags and returns plain text", () => {
    const htmlString =
      '<span style="color: red;">Error: Something went wrong</span>';
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`"Error: Something went wrong"`);
  });

  test("handles ANSI color span tags", () => {
    const htmlString =
      '<span style="color:#d03050;">ERROR</span>: <span style="color:#8ad03a;">File not found</span>';
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`"ERROR: File not found"`);
  });

  test("normalizes whitespace", () => {
    const htmlString = "<span>  Multiple   \n\n  spaces  and  \t tabs  </span>";
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`
      "  Multiple

        spaces  and  	 tabs"
    `);
  });

  test("handles empty HTML", () => {
    const htmlString = "";
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`""`);
  });

  test("handles plain text without HTML", () => {
    const htmlString = "Simple error message";
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`"Simple error message"`);
  });

  test("handles nested HTML elements", () => {
    const htmlString =
      '<div><span>Traceback:</span><pre><code>  File "test.py", line 1\n    print("hello"</code></pre></div>';
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`
      "Traceback:  File "test.py", line 1
          print("hello""
    `);
  });

  test("handles complex ANSI-converted HTML with styles", () => {
    const htmlString =
      '<span style="background:#fff;color:#000">  File "</span><span style="background:#fff;color:#0000ff">test.py</span><span style="background:#fff;color:#000">", line </span><span style="background:#fff;color:#008000">1</span>';
    const result = parseHtmlContent(htmlString);
    expect(result).toMatchInlineSnapshot(`"  File "test.py", line 1"`);
  });
});

describe("ansiToPlainText", () => {
  test("converts ANSI color codes to plain text", () => {
    const ansiString = "\u001B[31mError:\u001B[0m Something went wrong";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"Error: Something went wrong"`);
  });

  test("handles multiple ANSI color codes", () => {
    const ansiString =
      "\u001B[32mSUCCESS:\u001B[0m \u001B[34mOperation completed\u001B[0m successfully";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(
      `"SUCCESS: Operation completed successfully"`,
    );
  });

  test("handles ANSI bold and color combinations", () => {
    const ansiString =
      "\u001B[1;31mBOLD RED ERROR:\u001B[0m \u001B[33mWarning message\u001B[0m";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"BOLD RED ERROR: Warning message"`);
  });

  test("handles Python traceback with ANSI codes", () => {
    const ansiString =
      "\u001B[0;36m  File \"\u001B[0m\u001B[0;32mtest.py\u001B[0m\u001B[0;36m\", line \u001B[0m\u001B[0;32m1\u001B[0m\u001B[0;36m, in \u001B[0m\u001B[0;35m<module>\u001B[0m\n\u001B[0;31mNameError\u001B[0m: name 'undefined_var' is not defined";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "  File "test.py", line 1, in <module>
      NameError: name 'undefined_var' is not defined"
    `);
  });

  test("handles error messages with background colors", () => {
    const ansiString =
      "\u001B[41;37m CRITICAL ERROR \u001B[0m \u001B[31mSystem failure detected\u001B[0m";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(
      `" CRITICAL ERROR  System failure detected"`,
    );
  });

  test("handles complex stack trace with mixed formatting", () => {
    const ansiString =
      'Traceback (most recent call last):\n  \u001B[36mFile "\u001B[32m/path/to/file.py\u001B[36m", line \u001B[32m42\u001B[36m, in \u001B[35mfunction_name\u001B[0m\n    \u001B[31mraise ValueError("Something went wrong")\u001B[0m\n\u001B[31mValueError\u001B[0m: Something went wrong';
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "Traceback (most recent call last):
        File "/path/to/file.py", line 42, in function_name
          raise ValueError("Something went wrong")
      ValueError: Something went wrong"
    `);
  });

  test("handles empty string", () => {
    const ansiString = "";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`""`);
  });

  test("handles plain text without ANSI codes", () => {
    const ansiString = "Plain error message without colors";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(
      `"Plain error message without colors"`,
    );
  });

  test("handles whitespace and newlines correctly", () => {
    const ansiString =
      "\u001B[31m  Error:  \u001B[0m\n\n  \u001B[33m  Warning  \u001B[0m  ";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "  Error:

          Warning"
    `);
  });

  test("handles JavaScript error stack trace", () => {
    const ansiString =
      "\u001B[31mReferenceError\u001B[0m: \u001B[33mvariable\u001B[0m is not defined\n    at \u001B[36mObject.<anonymous>\u001B[0m (\u001B[32m/path/to/script.js\u001B[0m:\u001B[33m5\u001B[0m:\u001B[33m1\u001B[0m)";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "ReferenceError: variable is not defined
          at Object.<anonymous> (/path/to/script.js:5:1)"
    `);
  });

  test("handles Rust panic with ANSI formatting", () => {
    const ansiString =
      "thread '\u001B[32mmain\u001B[0m' panicked at '\u001B[31massertion failed: `(left == right)`\u001B[0m'\n  \u001B[36mleft\u001B[0m: `\u001B[33m5\u001B[0m`\n \u001B[36mright\u001B[0m: `\u001B[33m10\u001B[0m`";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "thread 'main' panicked at 'assertion failed: \`(left == right)\`'
        left: \`5\`
       right: \`10\`"
    `);
  });

  test("handles mix of 8-bit and 256-color ANSI codes", () => {
    const ansiString =
      "\u001B[38;5;196mBright Red\u001B[0m and \u001B[38;5;46mBright Green\u001B[0m text";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"Bright Red and Bright Green text"`);
  });
});

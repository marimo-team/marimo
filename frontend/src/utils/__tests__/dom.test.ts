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
    const ansiString = "\x1b[31mError:\x1b[0m Something went wrong";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"Error: Something went wrong"`);
  });

  test("handles multiple ANSI color codes", () => {
    const ansiString =
      "\x1b[32mSUCCESS:\x1b[0m \x1b[34mOperation completed\x1b[0m successfully";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(
      `"SUCCESS: Operation completed successfully"`,
    );
  });

  test("handles ANSI bold and color combinations", () => {
    const ansiString =
      "\x1b[1;31mBOLD RED ERROR:\x1b[0m \x1b[33mWarning message\x1b[0m";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"BOLD RED ERROR: Warning message"`);
  });

  test("handles Python traceback with ANSI codes", () => {
    const ansiString =
      "\x1b[0;36m  File \"\x1b[0m\x1b[0;32mtest.py\x1b[0m\x1b[0;36m\", line \x1b[0m\x1b[0;32m1\x1b[0m\x1b[0;36m, in \x1b[0m\x1b[0;35m<module>\x1b[0m\n\x1b[0;31mNameError\x1b[0m: name 'undefined_var' is not defined";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "  File "test.py", line 1, in <module>
      NameError: name 'undefined_var' is not defined"
    `);
  });

  test("handles error messages with background colors", () => {
    const ansiString =
      "\x1b[41;37m CRITICAL ERROR \x1b[0m \x1b[31mSystem failure detected\x1b[0m";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(
      `" CRITICAL ERROR  System failure detected"`,
    );
  });

  test("handles complex stack trace with mixed formatting", () => {
    const ansiString =
      'Traceback (most recent call last):\n  \x1b[36mFile "\x1b[32m/path/to/file.py\x1b[36m", line \x1b[32m42\x1b[36m, in \x1b[35mfunction_name\x1b[0m\n    \x1b[31mraise ValueError("Something went wrong")\x1b[0m\n\x1b[31mValueError\x1b[0m: Something went wrong';
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
      "\x1b[31m  Error:  \x1b[0m\n\n  \x1b[33m  Warning  \x1b[0m  ";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "  Error:

          Warning"
    `);
  });

  test("handles JavaScript error stack trace", () => {
    const ansiString =
      "\x1b[31mReferenceError\x1b[0m: \x1b[33mvariable\x1b[0m is not defined\n    at \x1b[36mObject.<anonymous>\x1b[0m (\x1b[32m/path/to/script.js\x1b[0m:\x1b[33m5\x1b[0m:\x1b[33m1\x1b[0m)";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "ReferenceError: variable is not defined
          at Object.<anonymous> (/path/to/script.js:5:1)"
    `);
  });

  test("handles Rust panic with ANSI formatting", () => {
    const ansiString =
      "thread '\x1b[32mmain\x1b[0m' panicked at '\x1b[31massertion failed: `(left == right)`\x1b[0m'\n  \x1b[36mleft\x1b[0m: `\x1b[33m5\x1b[0m`\n \x1b[36mright\x1b[0m: `\x1b[33m10\x1b[0m`";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`
      "thread 'main' panicked at 'assertion failed: \`(left == right)\`'
        left: \`5\`
       right: \`10\`"
    `);
  });

  test("handles mix of 8-bit and 256-color ANSI codes", () => {
    const ansiString =
      "\x1b[38;5;196mBright Red\x1b[0m and \x1b[38;5;46mBright Green\x1b[0m text";
    const result = ansiToPlainText(ansiString);
    expect(result).toMatchInlineSnapshot(`"Bright Red and Bright Green text"`);
  });
});

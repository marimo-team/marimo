/* Copyright 2024 Marimo. All rights reserved. */
import type { OutputMessage } from "@/core/kernel/messages";

export interface Cursor {
  row: number;
  col: number;
}

/**
 * A simplified terminal buffer.
 * It maintains an array of lines and grows as needed.
 */
export class TerminalBuffer {
  private lines: string[] = [""];
  private cursor: Cursor = { row: 0, col: 0 };
  // biome-ignore lint/suspicious/noControlCharactersInRegex: Needed for ANSI parsing
  private static readonly ESCAPE_REGEX = /\u001B\[([0-9;]*)([A-DJKH])/u;

  /** Ensure the internal lines array is large enough. */
  private ensureLine(row: number) {
    while (this.lines.length <= row) {
      this.lines.push("");
    }
  }

  /** Move cursor by relative offsets. */
  private moveCursor(rowDelta: number, colDelta: number) {
    const oldRow = this.cursor.row;
    this.cursor.row = Math.max(0, this.cursor.row + rowDelta);
    this.cursor.col = Math.max(0, this.cursor.col + colDelta);
    this.ensureLine(this.cursor.row);

    // When moving up, discard lines below the new cursor position
    // This simulates a fixed terminal window where tqdm overwrites content
    if (rowDelta < 0 && this.cursor.row < oldRow) {
      this.lines.splice(this.cursor.row + 1);
    }
  }

  /** Move cursor to a specific absolute position. */
  private setCursor(row: number, col: number) {
    this.cursor.row = Math.max(0, row);
    this.cursor.col = Math.max(0, col);
    this.ensureLine(this.cursor.row);
  }

  /** Write a visible character at the current cursor position. */
  writeChar(ch: string) {
    this.ensureLine(this.cursor.row);
    const line = this.lines[this.cursor.row];
    const padded = line.padEnd(this.cursor.col, " ");
    this.lines[this.cursor.row] =
      padded.slice(0, this.cursor.col) + ch + padded.slice(this.cursor.col + 1);
    this.cursor.col++;
  }

  /** Write a string of visible characters at the current cursor position (optimized batch write). */
  writeString(str: string) {
    if (str.length === 0) {
      return;
    }
    this.ensureLine(this.cursor.row);
    const line = this.lines[this.cursor.row];
    const padded = line.padEnd(this.cursor.col, " ");
    this.lines[this.cursor.row] =
      padded.slice(0, this.cursor.col) +
      str +
      padded.slice(this.cursor.col + str.length);
    this.cursor.col += str.length;
  }

  /** Handle simple control characters (\n, \r, \t, \b, \v). */
  control(ch: string) {
    switch (ch) {
      case "\n":
        this.cursor.row++;
        this.cursor.col = 0;
        this.ensureLine(this.cursor.row);
        break;
      case "\r":
        this.cursor.col = 0;
        break;
      case "\t":
        this.writeChar("\t");
        break;
      case "\b":
        this.cursor.col = Math.max(0, this.cursor.col - 1);
        break;
      case "\v":
        this.cursor.row++;
        this.ensureLine(this.cursor.row);
        break;
    }
  }

  /**
   * Handle a basic ANSI escape sequence.
   * Supports cursor movement and line erasing.
   */
  handleEscape(seq: string) {
    const match = TerminalBuffer.ESCAPE_REGEX.exec(seq);
    if (!match) {
      return;
    }

    const params = match[1]
      .split(";")
      .map((p) => (p === "" ? 1 : Number.parseInt(p, 10)));
    const code = match[2];

    switch (code) {
      case "A": // Cursor Up
        this.moveCursor(-params[0], 0);
        break;
      case "B": // Cursor Down
        this.moveCursor(params[0], 0);
        break;
      case "C": // Cursor Forward (Right)
        this.moveCursor(0, params[0]);
        break;
      case "D": // Cursor Back (Left)
        this.moveCursor(0, -params[0]);
        break;
      case "H": // Cursor Home
        this.setCursor(params[0] - 1 || 0, params[1] - 1 || 0);
        break;
      case "J": // Erase in display
        if (params[0] === 2) {
          this.lines = [""];
          this.setCursor(0, 0);
        }
        break;
      case "K": // Erase line
        this.ensureLine(this.cursor.row);
        switch (params[0]) {
          case 0:
            // Clear to end of line
            this.lines[this.cursor.row] = this.lines[this.cursor.row].slice(
              0,
              this.cursor.col,
            );

            break;

          case 1: {
            // Clear to start of line
            const len = this.lines[this.cursor.row].length;
            this.lines[this.cursor.row] =
              " ".repeat(this.cursor.col) +
              this.lines[this.cursor.row].slice(this.cursor.col, len);

            break;
          }
          case 2:
            this.lines[this.cursor.row] = "";

            break;

          // No default
        }
        break;
    }
  }

  /** Return the final rendered buffer as a single string. */
  render(): string {
    return this.lines.join("\n");
  }
}

/**
 * Parses ANSI escape sequences into tokens for processing.
 */
export class AnsiParser {
  // biome-ignore lint/suspicious/noControlCharactersInRegex: Needed for ANSI parsing
  private ESC_REGEX = /\u001B\[[0-9;]*[A-Za-z]/gu;

  parse(input: string): { type: "text" | "escape"; value: string }[] {
    const tokens: { type: "text" | "escape"; value: string }[] = [];
    let lastIndex = 0;

    for (const match of input.matchAll(this.ESC_REGEX)) {
      const index = match.index ?? 0;
      if (index > lastIndex) {
        tokens.push({ type: "text", value: input.slice(lastIndex, index) });
      }
      tokens.push({ type: "escape", value: match[0] });
      lastIndex = index + match[0].length;
    }

    if (lastIndex < input.length) {
      tokens.push({ type: "text", value: input.slice(lastIndex) });
    }

    return tokens;
  }
}

/**
 * High-level reducer that processes ANSI sequences and returns final visible output.
 * This class is stateful - it maintains the terminal buffer and cursor position across calls.
 * Use append() for streaming/incremental updates.
 */
export class AnsiReducer {
  private parser = new AnsiParser();
  private buffer = new TerminalBuffer();

  /**
   * Process the entire input string (replaces any previous state).
   * Use this for one-time processing or when starting fresh.
   */
  reduce(input: string): string {
    this.reset();
    this.append(input);
    return this.render();
  }

  /**
   * Append new input to the existing buffer (for streaming/incremental updates).
   * This is efficient for streaming scenarios - only processes the new chunk.
   */
  append(input: string): void {
    const tokens = this.parser.parse(input);

    // Fast path: if only one text token (no ANSI codes), handle directly
    if (tokens.length === 1 && tokens[0].type === "text") {
      const text = tokens[0].value;
      // Check if there are any control characters that need special handling
      if (!this.hasControlChars(text)) {
        // Simple text with no newlines or control chars - fastest path
        this.buffer.writeString(text);
        return;
      }
    }

    for (const token of tokens) {
      if (token.type === "text") {
        this.processText(token.value);
      } else {
        this.buffer.handleEscape(token.value);
      }
    }

    return;
  }

  /**
   * Reset the buffer and cursor to initial state.
   * Use this when you want to start processing fresh input.
   */
  reset(): void {
    this.buffer = new TerminalBuffer();
  }

  /**
   * Get the current rendered output without processing new input.
   */
  render(): string {
    return this.buffer.render();
  }

  /** Check if text contains control characters that need special handling. */
  private hasControlChars(text: string): boolean {
    for (const element of text) {
      if (element < " ") {
        return true;
      }
    }
    return false;
  }

  /** Process text token efficiently by batching writes when possible. */
  private processText(text: string) {
    let start = 0;
    const len = text.length;

    for (let i = 0; i < len; i++) {
      const ch = text[i];

      // Handle control characters
      if (
        ch === "\n" ||
        ch === "\r" ||
        ch === "\t" ||
        ch === "\b" ||
        ch === "\v"
      ) {
        // Write accumulated text before the control character
        if (i > start) {
          const segment = text.slice(start, i);
          // Filter out characters below space (but we already have \n, \r, \t, \b, \v handled)
          const filtered = this.filterControlChars(segment);
          if (filtered.length > 0) {
            this.buffer.writeString(filtered);
          }
        }
        this.buffer.control(ch);
        start = i + 1;
      } else if (ch < " ") {
        // Skip other control characters (below space)
        if (i > start) {
          const segment = text.slice(start, i);
          if (segment.length > 0) {
            this.buffer.writeString(segment);
          }
        }
        start = i + 1;
      }
    }

    // Write any remaining text
    if (start < len) {
      const segment = text.slice(start);
      const filtered = this.filterControlChars(segment);
      if (filtered.length > 0) {
        this.buffer.writeString(filtered);
      }
    }
  }

  /** Filter out control characters below space (except \n, \r, \t, \b, \v which are handled separately). */
  private filterControlChars(text: string): string {
    // Fast path: if no control chars, return as-is
    let hasControlChars = false;
    for (const element of text) {
      if (element < " ") {
        hasControlChars = true;
        break;
      }
    }

    if (!hasControlChars) {
      return text;
    }

    // Slow path: filter out control chars
    let result = "";
    for (const element of text) {
      if (element >= " ") {
        result += element;
      }
    }
    return result;
  }
}

export type StringOutputMessage = Omit<OutputMessage, "data"> & {
  data: string;
};

/**
 * Immutable output message that maintains ANSI state across appends.
 * This is used with react so must be immutable.
 */
export class StatefulOutputMessage implements OutputMessage {
  public readonly mimetype: OutputMessage["mimetype"];
  public readonly channel: OutputMessage["channel"];
  public readonly timestamp: OutputMessage["timestamp"];
  private ansiReducer = new AnsiReducer();
  private _data: string;

  public get data(): string {
    return this._data;
  }

  static create(message: StringOutputMessage): StatefulOutputMessage {
    const ansiReducer = new AnsiReducer();
    ansiReducer.append(message.data);
    return new StatefulOutputMessage(
      message.mimetype,
      message.channel,
      message.timestamp,
      ansiReducer,
    );
  }

  private constructor(
    mimetype: OutputMessage["mimetype"],
    channel: OutputMessage["channel"],
    timestamp: OutputMessage["timestamp"],
    ansiReducer: AnsiReducer,
  ) {
    this.mimetype = mimetype;
    this.channel = channel;
    this.timestamp = timestamp;
    this.ansiReducer = ansiReducer;
    this._data = this.ansiReducer.render();
  }

  appendData(chunk: string): StatefulOutputMessage {
    this.ansiReducer.append(chunk);
    return new StatefulOutputMessage(
      this.mimetype,
      this.channel,
      this.timestamp,
      this.ansiReducer,
    );
  }

  toJSON(): StringOutputMessage {
    return {
      mimetype: this.mimetype,
      channel: this.channel,
      timestamp: this.timestamp,
      data: this.data,
    };
  }
}

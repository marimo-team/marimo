/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Result of parsing Python code into a target language.
 */
export interface ParseResult<TMetadata = Record<string, unknown>> {
  /** The extracted code in the target language */
  code: string;
  /** Character offset from the start of the Python code where the extracted code begins */
  offset: number;
  /** Language-specific metadata extracted during parsing */
  metadata: TMetadata;
}

/**
 * Result of formatting target language code back into Python.
 */
export interface FormatResult {
  /** The formatted Python code */
  code: string;
  /** Character offset where the target language code begins (for cursor positioning) */
  offset: number;
}

/**
 * A language parser that can transform code between Python and a target language.
 * This is a stateless, framework-agnostic interface with no React or CodeMirror dependencies.
 *
 * @template TMetadata - The metadata type specific to this language
 */
export interface LanguageParser<TMetadata = Record<string, unknown>> {
  /** Unique identifier for this language parser */
  readonly type: string;

  /** Default Python code for this language */
  readonly defaultCode: string;

  /** Default metadata for this language */
  readonly defaultMetadata: Readonly<TMetadata>;

  /**
   * Transform Python code into the target language.
   *
   * @param pythonCode - The Python code to parse
   * @returns The extracted code, offset, and metadata
   */
  transformIn(pythonCode: string): ParseResult<TMetadata>;

  /**
   * Transform target language code back into Python.
   *
   * @param code - The target language code
   * @param metadata - The metadata from a previous transformIn call
   * @returns The formatted Python code and offset
   */
  transformOut(code: string, metadata: TMetadata): FormatResult;

  /**
   * Check if the given Python code is supported by this parser.
   *
   * @param pythonCode - The Python code to check
   * @returns true if this parser can handle the code
   */
  isSupported(pythonCode: string): boolean;
}

/**
 * Quote prefix types supported in Python strings.
 */
export const QUOTE_PREFIX_KINDS = ["", "f", "r", "fr", "rf"] as const;
export type QuotePrefixKind = (typeof QUOTE_PREFIX_KINDS)[number];

/**
 * Quote type (single, double, triple).
 */
export type QuoteType = '"' | "'" | '"""' | "'''";

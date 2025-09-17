/* Copyright 2024 Marimo. All rights reserved. */

// Edge case filenames for testing unicode, spaces, and special characters
export const EDGE_CASE_FILENAMES = [
  // Unicode
  "tést.py",
  "café.py",
  "测试.py",
  // Emojis
  "🚀notebook.py",
  // Spaces
  "test file.py",
  "file with spaces.py",
  // Multiple
  "café & 测试.py",
  "café notebook.py",
  // URL characters
  "test-file.py",
  "test_file.py",
  "test_file.backup.py",
  "file&with&ampersands.py",
  "file=with=equals.py",
  "file?with?questions.py",
];

// Cell names with unicode and special characters for frontend tests
export const EDGE_CASE_CELL_NAMES = [
  "tést_cell",
  "café_notebook",
  "测试_cell",
  "🚀_my_cell",
  "cell with spaces",
  "café notebook cell",
];

// URL test cases with special characters that could break query parameters
export const URL_SPECIAL_CHAR_FILENAMES = [
  "file with spaces.py",
  "file&with&ampersands.py",
  "file=with=equals.py",
  "file?with?questions.py",
  "café & 测试.py",
];

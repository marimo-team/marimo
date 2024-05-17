/* Copyright 2024 Marimo. All rights reserved. */
import {
  EditorSelection,
  SelectionRange,
  Text,
  Transaction,
} from "@codemirror/state";
import { EditorView } from "@codemirror/view";

function hasSelection(view: EditorView) {
  return !view.state.selection.main.empty;
}

function toggleAllLines(
  view: EditorView,
  selection: SelectionRange,
  markup: string,
) {
  const changes = [];
  let allLinesHaveMarkup = true;

  for (let pos = selection.from; pos <= selection.to; pos++) {
    const line = view.state.doc.lineAt(pos);
    const lineText = line.text;

    if (!lineText.startsWith(markup)) {
      allLinesHaveMarkup = false;
      break;
    }
  }

  for (let pos = selection.from; pos <= selection.to; ) {
    const line = view.state.doc.lineAt(pos);
    const lineText = line.text;

    const hasMarkup = lineText.startsWith(markup);

    if (allLinesHaveMarkup) {
      changes.push({
        from: line.from,
        to: line.from + markup.length,
        insert: Text.of([""]),
      });
    } else {
      if (hasMarkup) {
        changes.push({
          from: line.from,
          to: line.from + markup.length,
          insert: Text.of([""]),
        });
      }
      changes.push({
        from: line.from,
        insert: Text.of([markup]),
      });
    }

    pos = line.to + 1; // Move to the start of the next line
  }

  return changes;
}

function wrapWithMarkup(
  view: EditorView,
  range: SelectionRange,
  markupBefore: string,
  markupAfter: string,
) {
  if (range.empty) {
    const wordRange = view.state.wordAt(range.head);
    if (wordRange) {
      range = wordRange;
    }
  }

  const isMarkupBefore =
    view.state.sliceDoc(range.from - markupBefore.length, range.from) ===
    markupBefore;
  const isMarkupAfter =
    view.state.sliceDoc(range.to, range.to + markupAfter.length) ===
    markupAfter;
  const changes = [];

  changes.push(
    isMarkupBefore
      ? {
          from: range.from - markupBefore.length,
          to: range.from,
          insert: Text.of([""]),
        }
      : {
          from: range.from,
          insert: Text.of(markupBefore.split("\n")),
        },
    isMarkupAfter
      ? {
          from: range.to,
          to: range.to + markupAfter.length,
          insert: Text.of([""]),
        }
      : {
          from: range.to,
          insert: Text.of(markupAfter.split("\n")),
        },
  );

  const extendBefore = isMarkupBefore
    ? -markupBefore.length
    : markupBefore.length;
  const extendAfter = isMarkupAfter ? -markupAfter.length : markupAfter.length;

  return {
    changes,
    range: EditorSelection.range(
      range.from + extendBefore,
      range.to + extendAfter,
    ),
  };
}

export function insertBlockquote(view: EditorView) {
  // Only apply on selection
  if (!hasSelection(view)) {
    return false;
  }

  const markup = "> ";

  const changes = toggleAllLines(view, view.state.selection.main, markup);

  if (changes.length > 0) {
    view.dispatch(
      view.state.update({ changes, scrollIntoView: true, userEvent: "input" }),
    );
  }

  view.focus();

  return true;
}

export function insertBoldMarker(view: EditorView) {
  // Apply with or without selection

  const changes = view.state.changeByRange((range) => {
    if (range.empty) {
      const wordRange = view.state.wordAt(range.head);
      if (wordRange) {
        range = wordRange;
      }
    }

    return wrapWithMarkup(view, range, "**", "**");
  });

  view.dispatch(
    view.state.update(changes, {
      scrollIntoView: true,
      annotations: Transaction.userEvent.of("input"),
    }),
  );

  view.focus();

  return true;
}

export function insertCodeMarker(view: EditorView) {
  // Only apply on selection
  if (!hasSelection(view)) {
    return false;
  }

  const changes = view.state.changeByRange((range) => {
    if (range.empty) {
      const wordRange = view.state.wordAt(range.head);
      if (wordRange) {
        range = wordRange;
      }
    }
    const lineFrom = view.state.doc.lineAt(range.from).number;
    const lineTo = view.state.doc.lineAt(range.to).number;
    const isMultiline = lineFrom !== lineTo;
    const fenceBefore = isMultiline ? "```\n" : "`";
    const fenceAfter = isMultiline ? "\n```" : "`";

    return wrapWithMarkup(view, range, fenceBefore, fenceAfter);
  });

  view.dispatch(
    view.state.update(changes, {
      scrollIntoView: true,
      annotations: Transaction.userEvent.of("input"),
    }),
  );

  view.focus();

  return true;
}

export function insertItalicMarker(view: EditorView) {
  // Apply with or without selection

  const changes = view.state.changeByRange((range) => {
    if (range.empty) {
      const wordRange = view.state.wordAt(range.head);
      if (wordRange) {
        range = wordRange;
      }
    }

    return wrapWithMarkup(view, range, "_", "_");
  });

  view.dispatch(
    view.state.update(changes, {
      scrollIntoView: true,
      annotations: Transaction.userEvent.of("input"),
    }),
  );

  view.focus();

  return true;
}

export function insertLink(view: EditorView, url = "http://") {
  // Only apply on selection
  if (!hasSelection(view)) {
    return false;
  }

  const changes = view.state.changeByRange((range) => {
    const text = view.state.sliceDoc(range.from, range.to);
    return {
      changes: [
        { from: range.from, to: range.to, insert: `[${text}](${url})` },
      ],
      range,
    };
  });

  view.dispatch(
    view.state.update(changes, {
      scrollIntoView: true,
      annotations: Transaction.userEvent.of("input"),
    }),
  );

  const { to } = changes.selection.main;
  // Can fail in tests
  try {
    view.dispatch({
      selection: EditorSelection.create([
        EditorSelection.range(to + 3, to + 3 + url.length),
        EditorSelection.cursor(to + 3 + url.length),
      ]),
    });
  } catch {
    // Do nothing
  }

  view.focus();

  return true;
}

export function insertUL(view: EditorView) {
  // Only apply on selection
  if (!hasSelection(view)) {
    return false;
  }

  const { changes } = view.state.changeByRange((range) => {
    const markupOne = `- `;
    const markupTwo = `* `;

    const rangeText = view.state
      .sliceDoc(range.from, range.to + markupTwo.length)
      .startsWith(markupTwo)
      ? markupTwo
      : markupOne;

    return {
      range,
      changes: toggleAllLines(view, range, rangeText),
    };
  });

  if (changes.length > 0) {
    view.dispatch(
      view.state.update({ changes, scrollIntoView: true, userEvent: "input" }),
    );
  }
  view.focus();

  return true;
}

export function insertOL(view: EditorView) {
  // Only apply on selection
  if (!hasSelection(view)) {
    return false;
  }

  const { changes } = view.state.changeByRange((range) => {
    const markup = "1. ";
    return {
      range,
      changes: toggleAllLines(view, range, markup),
    };
  });

  if (changes.length > 0) {
    view.dispatch(
      view.state.update({ changes, scrollIntoView: true, userEvent: "input" }),
    );
  }

  view.focus();

  return true;
}

/* Copyright 2024 Marimo. All rights reserved. */
import "./styles.css";
import {
  EditorView,
  Decoration,
  type DecorationSet,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
  keymap,
} from "@codemirror/view";
import {
  StateField,
  StateEffect,
  EditorSelection,
  type Range,
  Prec,
  type Extension,
} from "@codemirror/state";
import { getSymbol } from "../../../components/shortcuts/renderShortcut";
import { Logger } from "@/utils/Logger";
import { toast } from "@/components/ui/use-toast";

export type CompleteFunction = (opts: {
  prompt: string;
  editorView: EditorView;
  selection: string;
  codeBefore: string;
  codeAfter: string;
}) => Promise<string>;

/**
 * The prompt extension creates a plugin for CodeMirror that adds AI-assisted editing functionality.
 *
 * Key features and behaviors:
 * 1. Cmd+L Tooltip:
 *    - Appears when text is selected.
 *    - Hidden when:
 *      a) No text is selected
 *      b) Editing instructions input is open
 *      c) A completion is pending (not yet accepted or declined)
 *
 * 2. Editing Instructions Input:
 *    - Opened with Cmd+L when text is selected
 *    - Automatically focused when opened
 *    - Closed with Escape key
 *
 * 3. Completions:
 *    - Displayed after submitting editing instructions
 *    - Can be accepted with Cmd+Y or the accept button
 *    - Can be rejected with Cmd+U or the reject button
 *
 * 4. States:
 *    - tooltipState: Manages visibility of Cmd+L tooltip
 *    - inputState: Manages visibility and position of editing instructions input
 *    - completionState: Manages the current completion (if any)
 *
 * This plugin ensures that only one of these elements (tooltip, input, or completion)
 * is visible at any given time, providing a clear and focused user experience.
 */
export function promptPlugin(opts: {
  complete: CompleteFunction;
}): Extension[] {
  const { complete } = opts;
  return [
    tooltipState,
    inputState,
    completionState,
    loadingState,
    selectionPlugin,
    keymap.of([
      {
        key: "Mod-l",
        run: showInputPrompt,
      },
    ]),
    Prec.highest([
      keymap.of([
        { key: "Mod-y", run: acceptCompletion },
        { key: "Mod-u", run: rejectCompletion },
      ]),
    ]),
    EditorView.updateListener.of((update) => {
      if (update.selectionSet) {
        const { from, to } = update.state.selection.main;
        const inputStateValue = update.state.field(inputState);
        const completionStateValue = update.state.field(completionState);
        // Only show tooltip if there's a selection and no input or completion is active
        update.view.dispatch({
          effects: showTooltip.of(
            from !== to && !inputStateValue.show && !completionStateValue,
          ),
        });
      }
    }),
    EditorView.decorations.of((view) => {
      const inputStateValue = view.state.field(inputState);
      const completionStateValue = view.state.field(completionState);
      const decorations: Array<Range<Decoration>> = [];

      if (inputStateValue.show) {
        for (let i = inputStateValue.from; i < inputStateValue.to; i++) {
          decorations.push(
            Decoration.line({ class: "cm-ai-selection" }).range(i),
          );
          if (i === inputStateValue.from) {
            decorations.push(
              Decoration.widget({
                widget: new InputWidget(complete),
                side: -1,
              }).range(inputStateValue.from),
            );
          }
        }
      }

      if (completionStateValue) {
        decorations.push(
          Decoration.widget({
            widget: new OldCodeWidget(view, completionStateValue.oldCode),
            side: -1,
          }).range(completionStateValue.from),
          Decoration.mark({
            class: "cm-new-code-line",
          }).range(completionStateValue.from, completionStateValue.to),
        );
      }

      return Decoration.set(decorations);
    }),
  ];
}

// Singleton tooltip element
let tooltip: HTMLDivElement;

// State effect to show/hide the tooltip
const showTooltip = StateEffect.define<boolean>();

// State field to manage the tooltip visibility
const tooltipState = StateField.define<boolean>({
  create() {
    return false;
  },
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(showTooltip)) {
        return e.value;
      }
    }
    return value;
  },
});

// View plugin to handle selection changes
const selectionPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = this.createDecorations(view);
    }

    update(update: ViewUpdate) {
      if (
        update.selectionSet ||
        update.docChanged ||
        update.viewportChanged ||
        update.transactions.some((tr) =>
          tr.effects.some((e) => e.is(showTooltip)),
        )
      ) {
        this.decorations = this.createDecorations(update.view);
      }
    }

    createDecorations(view: EditorView) {
      const { from, to } = view.state.selection.main;
      const inputStateValue = view.state.field(inputState);
      const completionStateValue = view.state.field(completionState);
      const tooltipStateValue = view.state.field(tooltipState);
      const doc = view.state.doc;

      // Hide tooltip if there's no selection, input is open, completion is pending, or tooltipState is false
      if (
        from === to ||
        inputStateValue.show ||
        completionStateValue ||
        !tooltipStateValue ||
        from < 0 ||
        to > doc.length
      ) {
        return Decoration.none;
      }

      // Adjust selection to exclude empty lines at the start and end
      let adjustedFrom = from;
      let adjustedTo = to;

      while (
        adjustedFrom < adjustedTo &&
        doc.lineAt(adjustedFrom).length === 0
      ) {
        adjustedFrom = doc.lineAt(adjustedFrom + 1).from;
      }
      while (adjustedTo > adjustedFrom && doc.lineAt(adjustedTo).length === 0) {
        adjustedTo = doc.lineAt(adjustedTo - 1).to;
      }

      // If the adjusted selection is empty, don't show the tooltip
      if (adjustedFrom === adjustedTo) {
        return Decoration.none;
      }

      if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.className = "cm-tooltip cm-ai-tooltip";
        tooltip.innerHTML = `<span>Edit <span Loadingclass="hotkey">${getSymbol("mod") ?? "Ctrl"} + L</span></span>`;
        tooltip.style.cursor = "pointer";
        tooltip.addEventListener("click", (evt) => {
          evt.stopPropagation();
          showInputPrompt(view);
        });
      }

      return Decoration.set([
        Decoration.widget({
          widget: new (class extends WidgetType {
            toDOM() {
              return tooltip;
            }
            override ignoreEvent() {
              return true;
            }
          })(),
          side: -1,
        }).range(adjustedFrom),
      ]);
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);

const showInput = StateEffect.define<{
  show: boolean;
  from: number;
  to: number;
}>();

const inputState = StateField.define<{
  show: boolean;
  from: number;
  to: number;
}>({
  create() {
    return { show: false, from: 0, to: 0 };
  },
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(showInput)) {
        return e.value;
      }
    }
    return value;
  },
});

const showCompletion = StateEffect.define<{
  from: number;
  to: number;
  oldCode: string;
  newCode: string;
} | null>();

const completionState = StateField.define<{
  from: number;
  to: number;
  oldCode: string;
  newCode: string;
} | null>({
  create() {
    return null;
  },
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(showCompletion)) {
        return e.value;
      }
    }
    return value;
  },
});

// Add a new state effect and state field for loading status
const setLoading = StateEffect.define<boolean>();

const loadingState = StateField.define<boolean>({
  create() {
    return false;
  },
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(setLoading)) {
        return e.value;
      }
    }
    return value;
  },
});

function showInputPrompt(view: EditorView) {
  const { state } = view;
  const selection = state.selection.main;
  if (selection.from !== selection.to) {
    const doc = state.doc;
    const fromLine = doc.lineAt(selection.from);
    const toLine = doc.lineAt(selection.to);
    const docLength = doc.length;

    // Ensure the selection is within the document bounds
    const safeFrom = Math.max(0, Math.min(fromLine.from, docLength));
    const safeTo = Math.max(0, Math.min(toLine.to, docLength));

    view.dispatch({
      effects: [
        showInput.of({
          show: true,
          from: safeFrom,
          to: safeTo,
        }),
        showTooltip.of(false), // Hide the tooltip
      ],
      selection: EditorSelection.cursor(safeFrom),
    });
    return true;
  }
  return false;
}

function acceptCompletion(view: EditorView) {
  const completionStateValue = view.state.field(completionState);
  if (completionStateValue) {
    view.dispatch({
      effects: [
        showCompletion.of(null),
        showInput.of({ show: false, from: 0, to: 0 }),
        setLoading.of(false),
      ],
    });
    return true;
  }
  return false;
}

function rejectCompletion(view: EditorView) {
  const completionStateValue = view.state.field(completionState);
  if (completionStateValue) {
    view.dispatch({
      changes: {
        from: completionStateValue.from,
        to: completionStateValue.to,
        insert: completionStateValue.oldCode,
      },
      effects: [
        showCompletion.of(null),
        showInput.of({ show: false, from: 0, to: 0 }),
        setLoading.of(false),
      ],
    });
    return true;
  }
  return false;
}

// Update the OldCodeWidget class
class OldCodeWidget extends WidgetType {
  constructor(
    private view: EditorView,
    private oldCode: string,
  ) {
    super();
  }
  toDOM() {
    const container = document.createElement("div");
    container.className = "cm-old-code-container";

    const oldCodeEl = document.createElement("div");
    oldCodeEl.className = "cm-old-code";
    oldCodeEl.textContent = this.oldCode;
    container.append(oldCodeEl);

    const buttonsContainer = document.createElement("div");
    buttonsContainer.className = "cm-floating-buttons";

    const modSymbol = getSymbol("mod") ?? "Ctrl";

    const acceptButton = document.createElement("button");
    acceptButton.textContent = `${modSymbol} Y`;
    acceptButton.className = "cm-floating-button cm-floating-accept";
    acceptButton.addEventListener("click", () => acceptCompletion(this.view));

    const rejectButton = document.createElement("button");
    rejectButton.textContent = `${modSymbol} U`;
    rejectButton.className = "cm-floating-button cm-floating-reject";
    rejectButton.addEventListener("click", () => rejectCompletion(this.view));

    buttonsContainer.append(acceptButton);
    buttonsContainer.append(rejectButton);
    container.append(buttonsContainer);

    return container;
  }
}

// Input widget
class InputWidget extends WidgetType {
  constructor(private complete: CompleteFunction) {
    super();
  }

  toDOM(view: EditorView) {
    const inputContainer = document.createElement("div");
    inputContainer.className = "cm-ai-input-container";

    const input = document.createElement("input");
    input.className = "cm-ai-input";
    input.placeholder = "Editing instructions...";

    const loadingIndicator = document.createElement("div");
    loadingIndicator.classList.add("cm-ai-loading-indicator");
    loadingIndicator.textContent = "Loading";
    const isLoading = view.state.field(loadingState);

    const helpInfo = document.createElement("div");
    helpInfo.className = "cm-ai-help-info";
    helpInfo.textContent = "Esc to close";

    if (isLoading) {
      helpInfo.classList.add("hidden");
    } else {
      loadingIndicator.classList.add("hidden");
    }

    // Set up a timeout to focus the input after it's been added to the DOM
    setTimeout(() => input.focus(), 0);

    input.addEventListener("keydown", async (e) => {
      if (e.key === "Enter") {
        const state = view.state.field(inputState);
        const oldCode = view.state.sliceDoc(state.from, state.to);
        const codeBefore = view.state.sliceDoc(0, state.from);
        const codeAfter = view.state.sliceDoc(state.to);

        // Show loading indicator
        view.dispatch({ effects: setLoading.of(true) });
        loadingIndicator.classList.remove("hidden");
        helpInfo.classList.add("hidden");
        input.disabled = true;

        try {
          const result = await this.complete({
            prompt: input.value,
            selection: oldCode,
            codeBefore: codeBefore,
            codeAfter: codeAfter,
            editorView: view,
          });

          if (!view.state.field(inputState).show) {
            return;
          }

          view.dispatch({
            changes: { from: state.from, to: state.to, insert: result },
            effects: [
              showInput.of({ show: false, from: state.from, to: state.to }),
              showCompletion.of({
                from: state.from,
                to: state.from + result.length,
                oldCode,
                newCode: result,
              }),
              setLoading.of(false),
            ],
            selection: EditorSelection.cursor(state.to),
          });
        } catch (error) {
          Logger.error("Completion error:", error);
          toast({
            title: "Error",
            description:
              "An error occurred while processing your request. Please try again.",
            variant: "danger",
          });
        } finally {
          // Hide loading indicator
          loadingIndicator.classList.add("hidden");
          helpInfo.classList.remove("hidden");
          input.disabled = false;
        }

        // Refocus the editor after the prompt returns
        view.focus();
      } else if (e.key === "Escape") {
        // Close the input when Escape is pressed
        view.dispatch({
          effects: [
            showInput.of({ show: false, from: 0, to: 0 }),
            setLoading.of(false),
          ],
        });
        // Refocus the editor after closing the input
        view.focus();
      }
    });

    inputContainer.append(input, loadingIndicator, helpInfo);

    return inputContainer;
  }
}

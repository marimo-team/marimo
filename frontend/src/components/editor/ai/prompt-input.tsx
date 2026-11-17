/* Copyright 2026 Marimo. All rights reserved. */

import {
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { markdown } from "@codemirror/lang-markdown";
import { Prec } from "@codemirror/state";
import { promptHistory } from "@marimo-team/codemirror-ai";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import { useStore } from "jotai";
import { useMemo } from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
import { resourceExtension } from "@/core/codemirror/ai/resources";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { ZodLocalStorage } from "@/utils/storage/typed";
import { CONTEXT_TRIGGER, mentionsCompletionSource } from "./completion-utils";

const KEY = "marimo:ai-prompt-history";
const promptHistoryStorage = new ZodLocalStorage(z.array(z.string()), () => []);

export interface AdditionalCompletions {
  triggerCompletionRegex: RegExp;
  completions: Completion[];
}

interface PromptInputProps {
  inputRef?: React.RefObject<ReactCodeMirrorRef | null>;
  placeholder?: string;
  value: string;
  className?: string;
  onKeyDown?: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  onClose: () => void;
  onChange: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  additionalCompletions?: AdditionalCompletions;
  maxHeight?: string;
  onAddFiles?: (files: File[]) => void;
}

/**
 * CodeMirror-based input for the AI prompt.
 *
 * This is just text (no language support), but we use codemirror to get autocomplete
 * for @dataframe and @sql_table.
 */
export const PromptInput = ({
  value,
  placeholder,
  inputRef,
  className,
  onChange,
  onSubmit,
  onKeyDown,
  onClose,
  onAddFiles,
  additionalCompletions,
  maxHeight,
}: PromptInputProps) => {
  const handleSubmit = useEvent(onSubmit);
  const handleEscape = useEvent(onClose);
  const store = useStore();
  const { theme } = useTheme();

  const additionalCompletionsSource: CompletionSource = useEvent(
    (context: CompletionContext) => {
      if (!additionalCompletions) {
        return null;
      }

      return mentionsCompletionSource(
        [additionalCompletions.triggerCompletionRegex],
        additionalCompletions.completions,
      )(context);
    },
  );

  // Changing extensions can be expensive, so
  // it is worth making sure this is memoized well.
  const extensions = useMemo(() => {
    const markdownLanguage = markdown();
    return [
      autocompletion({}),
      markdownLanguage,
      resourceExtension({
        language: markdownLanguage.language,
        store,
        onAddFiles,
      }),
      markdownLanguage.language.data.of({
        autocomplete: additionalCompletionsSource,
      }),
      promptHistory({
        storage: {
          load: () => promptHistoryStorage.get(KEY),
          save: (prompts) => promptHistoryStorage.set(KEY, prompts),
        },
      }),
      EditorView.lineWrapping,
      minimalSetup(),
      Prec.highest(
        keymap.of([
          {
            preventDefault: true,
            stopPropagation: true,
            any: (view, event) => {
              const pressedModOrShift =
                event.metaKey || event.ctrlKey || event.shiftKey;
              // If no mod key is pressed, submit
              if (event.key === "Enter" && !pressedModOrShift) {
                handleSubmit(event, view.state.doc.toString());
                event.preventDefault();
                event.stopPropagation();
                return true;
              }
              // Mod+Enter does add a new line already by codemirror
              // But Shift+Enter does not, so we need to handle it manually
              if (event.key === "Enter" && event.shiftKey) {
                view.dispatch(view.state.replaceSelection("\n"));
                event.preventDefault();
                event.stopPropagation();
                return true;
              }

              return false;
            },
          },
        ]),
      ),
      keymap.of([
        {
          key: "Escape",
          preventDefault: true,
          stopPropagation: true,
          run: () => {
            handleEscape();
            return true;
          },
        },
      ]),
    ];
  }, [
    store,
    onAddFiles,
    additionalCompletionsSource,
    handleSubmit,
    handleEscape,
  ]);

  return (
    <ReactCodeMirror
      ref={inputRef}
      className={cn(
        "mo-ai-prompt flex-1 font-sans text-sm leading-6 overflow-auto my-1",
        className,
      )}
      width="100%"
      maxHeight={maxHeight}
      value={value}
      basicSetup={false}
      extensions={extensions}
      onChange={onChange}
      onKeyDown={onKeyDown}
      theme={theme === "dark" ? "dark" : "light"}
      placeholder={
        placeholder || `Generate with AI, ${CONTEXT_TRIGGER} to include context`
      }
    />
  );
};

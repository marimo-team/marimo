/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "../types";

import { Labeled } from "./common/labeled";
import { type Theme, useTheme } from "@/theme/useTheme";
import { LazyAnyLanguageCodeMirror } from "./code/LazyAnyLanguageCodeMirror";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useCallback, useState, useMemo } from "react";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { EditorView } from "@codemirror/view";
import useEvent from "react-use-event-hook";

type T = string;

interface Data {
  language: string;
  placeholder: string;
  theme?: Theme;
  label: string | null;
  disabled?: boolean;
  minHeight?: number;
  maxHeight?: number;
  showCopyButton?: boolean;
  debounce: boolean | number;
}

export class CodeEditorPlugin implements IPlugin<T, Data> {
  tagName = "marimo-code-editor";

  validator = z.object({
    initialValue: z.string(),
    language: z.string().default("python"),
    placeholder: z.string(),
    theme: z.enum(["light", "dark"]).optional(),
    label: z.string().nullable(),
    disabled: z.boolean().optional(),
    minHeight: z.number().optional(),
    maxHeight: z.number().optional(),
    showCopyButton: z.boolean().optional(),
    debounce: z.union([z.boolean(), z.number()]).default(false),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <CodeEditorComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface CodeEditorComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const CodeEditorComponent = (props: CodeEditorComponentProps) => {
  const { theme } = useTheme();
  const finalTheme = props.theme || theme;
  const minHeight = props.minHeight ? `${props.minHeight}px` : "70px";
  const maxHeight = props.maxHeight ? `${props.maxHeight}px` : undefined;

  const [localValue, setLocalValue] = useState(props.value);
  const { onChange: setValueDebounced } = useDebounceControlledState<string>({
    initialValue: props.value,
    delay: Number.isFinite(props.debounce) ? (props.debounce as number) : 0,
    onChange: props.setValue,
    disabled: !Number.isFinite(props.debounce),
  });

  const handleChange = useCallback(
    (newValue: string) => {
      setLocalValue((_) => newValue);
      if (typeof props.debounce === "number") {
        setValueDebounced(newValue);
      } else if (!props.debounce) {
        props.setValue(newValue);
      }
    },
    [setValueDebounced, props.debounce, props.setValue],
  );

  const onBlur = useEvent(() => {
    props.setValue(localValue);
  });

  const extensions = useMemo(() => {
    if (props.debounce === true) {
      return [EditorView.domEventHandlers({ blur: onBlur })];
    }

    return [];
  }, [props.debounce, onBlur]);

  return (
    <TooltipProvider>
      <Labeled label={props.label} align="top" fullWidth={true}>
        <LazyAnyLanguageCodeMirror
          className={`cm [&>*]:outline-none border rounded overflow-hidden ${finalTheme}`}
          theme={finalTheme === "dark" ? "dark" : "light"}
          minHeight={minHeight}
          maxHeight={maxHeight}
          placeholder={props.placeholder}
          editable={!props.disabled}
          value={localValue}
          language={props.language}
          onChange={handleChange}
          showCopyButton={props.showCopyButton}
          extensions={extensions}
        />
      </Labeled>
    </TooltipProvider>
  );
};

/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "../types";

import { Labeled } from "./common/labeled";
import { type Theme, useTheme } from "@/theme/useTheme";
import { LazyAnyLanguageCodeMirror } from "./code/LazyAnyLanguageCodeMirror";

type T = string;

interface Data {
  language: string;
  placeholder: string;
  theme?: Theme;
  label: string | null;
  disabled?: boolean;
  minHeight?: number;
  maxHeight?: number;
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

  return (
    <Labeled label={props.label} align="top" fullWidth={true}>
      <LazyAnyLanguageCodeMirror
        className={`cm [&>*]:outline-none border rounded overflow-hidden ${finalTheme}`}
        theme={finalTheme === "dark" ? "dark" : "light"}
        minHeight={minHeight}
        maxHeight={maxHeight}
        placeholder={props.placeholder}
        editable={!props.disabled}
        value={props.value}
        language={props.language}
        onChange={props.setValue}
      />
    </Labeled>
  );
};

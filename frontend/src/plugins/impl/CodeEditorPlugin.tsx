/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Labeled } from "./common/labeled";
import { Theme, getTheme } from "@/theme/useTheme";
import { lazy } from "react";

type T = string;

interface Data {
  language: string;
  placeholder: string;
  theme: Theme;
  label: string | null;
  disabled?: boolean;
  minHeight?: number;
}

export class CodeEditorPlugin implements IPlugin<T, Data> {
  tagName = "marimo-code-editor";

  validator = z.object({
    initialValue: z.string(),
    language: z.string().default("python"),
    placeholder: z.string(),
    theme: z.enum(["light", "dark"]).default("light"),
    label: z.string().nullable(),
    disabled: z.boolean().optional(),
    minHeight: z.number().optional(),
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

const LazyAnyLanguageCodeMirror = lazy(
  () => import("./code/any-language-editor")
);

interface CodeEditorComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const CodeEditorComponent = (props: CodeEditorComponentProps) => {
  const theme = props.theme || getTheme();
  const minHeight = props.minHeight ? `${props.minHeight}px` : "70px";

  return (
    <Labeled label={props.label} align="top">
      <LazyAnyLanguageCodeMirror
        className={`cm [&>*]:outline-none border rounded overflow-hidden ${theme}`}
        theme={theme === "dark" ? "dark" : "light"}
        minHeight={minHeight}
        placeholder={props.placeholder}
        editable={!props.disabled}
        value={props.value}
        language={props.language}
        onChange={(value) => props.setValue(value)}
      />
    </Labeled>
  );
};

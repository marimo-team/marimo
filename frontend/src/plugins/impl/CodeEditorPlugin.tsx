/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Labeled } from "./common/labeled";
import { Theme, getTheme } from "@/theme/useTheme";
import ReactCodeMirror from "@uiw/react-codemirror";
import { loadLanguage, langs } from "@uiw/codemirror-extensions-langs";

type T = string;

type Lang = keyof typeof langs;

interface Data {
  language: Lang;
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
    language: z.enum(Object.keys(langs) as [Lang]),
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

interface CodeEditorComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const CodeEditorComponent = (props: CodeEditorComponentProps) => {
  const theme = props.theme || getTheme();
  const minHeight = props.minHeight ? `${props.minHeight}px` : "70px";

  return (
    <Labeled label={props.label} align="top">
      <ReactCodeMirror
        className={`cm [&>*]:outline-none border rounded overflow-hidden ${theme}`}
        theme={theme === "dark" ? "dark" : "light"}
        minHeight={minHeight}
        placeholder={props.placeholder}
        editable={!props.disabled}
        value={props.value}
        extensions={[loadLanguage(props.language)].filter(Boolean)}
        onChange={(value) => props.setValue(value)}
      />
    </Labeled>
  );
};

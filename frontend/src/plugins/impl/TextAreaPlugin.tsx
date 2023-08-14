/* Copyright 2023 Marimo. All rights reserved. */
import { Label } from "../../components/ui/label";
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { HtmlOutput } from "../../editor/output/HtmlOutput";
import * as labelStyles from "./Label.styles";
import { Textarea } from "../../components/ui/textarea";

type T = string;

interface Data {
  placeholder: string;
  label: string | null;
}

export class TextAreaPlugin implements IPlugin<T, Data> {
  tagName = "marimo-text-area";

  validator = z.object({
    initialValue: z.string(),
    placeholder: z.string(),
    label: z.string().nullable(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TextAreaComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface TextAreaComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const TextAreaComponent = (props: TextAreaComponentProps) => {
  const labelElement =
    props.label === null ? null : (
      <Label className="text-md">
        <HtmlOutput html={props.label} />
      </Label>
    );

  return (
    <div className={labelStyles.labelContainerBlock}>
      {labelElement}
      <Textarea
        className="mt-3"
        style={{
          fontFamily: "var(--monospace-font)",
        }}
        rows={5}
        cols={33}
        value={props.value}
        onInput={(event) =>
          props.setValue((event.target as HTMLInputElement).value)
        }
        placeholder={props.placeholder}
      />
    </div>
  );
};

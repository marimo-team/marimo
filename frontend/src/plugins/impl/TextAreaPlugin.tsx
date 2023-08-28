/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Textarea } from "../../components/ui/textarea";
import { Labeled } from "./common/labeled";

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
  return (
    <Labeled label={props.label} align="top">
      <Textarea
        className="font-code"
        rows={5}
        cols={33}
        value={props.value}
        onInput={(event) =>
          props.setValue((event.target as HTMLInputElement).value)
        }
        placeholder={props.placeholder}
      />
    </Labeled>
  );
};

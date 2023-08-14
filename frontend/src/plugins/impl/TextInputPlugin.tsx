/* Copyright 2023 Marimo. All rights reserved. */
import { Label } from "../../components/ui/label";
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { HtmlOutput } from "../../editor/output/HtmlOutput";
import * as labelStyles from "./Label.styles";
import { Input } from "../../components/ui/input";
import { cn } from "../../lib/utils";
import { AtSignIcon, GlobeIcon, LockIcon } from "lucide-react";
import { useState } from "react";

type T = string;

type InputType = "text" | "password" | "email" | "url";

interface Data {
  placeholder: string;
  label: string | null;
  kind: InputType;
}

export class TextInputPlugin implements IPlugin<T, Data> {
  tagName = "marimo-text";

  validator = z.object({
    initialValue: z.string(),
    placeholder: z.string(),
    label: z.string().nullable(),
    kind: z.enum(["text", "password", "email", "url"]).default("text"),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TextComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface TextComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const TextComponent = (props: TextComponentProps) => {
  const [valueOnBlur, setValueOnBlur] = useState(props.value);

  const labelElement =
    props.label === null ? null : (
      <Label className={labelStyles.label}>
        <HtmlOutput html={props.label} inline={true} />
      </Label>
    );

  const valueToValidate = valueOnBlur == null ? props.value : valueOnBlur;
  const isValid = validate(props.kind, valueToValidate);

  const icon: Record<InputType, JSX.Element | null> = {
    text: null,
    password: <LockIcon size={16} />,
    email: <AtSignIcon size={16} />,
    url: <GlobeIcon size={16} />,
  };

  return (
    <div className={labelStyles.labelContainer}>
      {labelElement}
      <Input
        type={props.kind}
        icon={icon[props.kind]}
        placeholder={props.placeholder}
        className={cn({
          "border-destructive": !isValid,
        })}
        value={props.value}
        onInput={(event) => props.setValue(event.currentTarget.value)}
        onBlur={(event) => setValueOnBlur(event.currentTarget.value)}
      />
    </div>
  );
};

function validate(kind: InputType, value: string): boolean {
  // We don't validate required-ness to empty is valid
  if (!value) {
    return true;
  }

  // We only validate email and url types
  switch (kind) {
    case "email":
      return z.string().email().safeParse(value).success;
    case "url":
      return z.string().url().safeParse(value).success;
    default:
      return true;
  }
}

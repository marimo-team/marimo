/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import { Button } from "../../components/ui/button";
import { renderHTML } from "../core/RenderHTML";
import { Intent, zodIntent } from "./common/intent";

interface Data {
  label: string;
  kind: Intent;
  disabled: boolean;
}

export class ButtonPlugin implements IPlugin<number, Data> {
  tagName = "marimo-button";

  validator = z.object({
    label: z.string(),
    kind: zodIntent,
    disabled: z.boolean().default(false),
  });

  render(props: IPluginProps<number, Data>): JSX.Element {
    const {
      data: { disabled, kind, label },
    } = props;
    // value counts number of times button was clicked
    return (
      <Button
        variant={kindToButtonVariant(kind)}
        disabled={disabled}
        size="xs"
        onClick={() => {
          if (disabled) {
            return;
          }
          props.setValue((v) => v + 1);
        }}
        type="submit"
      >
        {renderHTML({ html: label })}
      </Button>
    );
  }
}

function kindToButtonVariant(kind: Intent) {
  switch (kind) {
    case "neutral":
      return "secondary";
    case "danger":
      return "destructive";
    case "warn":
      return "warn";
    case "success":
      return "success";
  }
}

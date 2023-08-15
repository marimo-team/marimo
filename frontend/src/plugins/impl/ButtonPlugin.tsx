/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import { Button } from "../../components/ui/button";
import { renderHTML } from "../core/RenderHTML";

export class ButtonPlugin implements IPlugin<number, { label: string }> {
  tagName = "marimo-button";

  validator = z.object({ initialValue: z.number(), label: z.string() });

  render(props: IPluginProps<number, { label: string }>): JSX.Element {
    // value counts number of times button was clicked
    return (
      <Button
        variant="secondary"
        size="xs"
        onClick={() => props.setValue((v) => v + 1)}
        type="submit"
      >
        {renderHTML({ html: props.data.label })}
      </Button>
    );
  }
}

/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { renderHTML } from "../core/RenderHTML";

interface Data {
  /**
   * The labels for each item; raw HTML.
   */
  labels: string[];

  /**
   * Whether to allow multiple tabs to be open.
   */
  multiple: boolean;
}

export class AccordionPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-accordion";

  validator = z.object({
    labels: z.array(z.string()),
    multiple: z.boolean(),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <AccordionComponent {...props.data}>{props.children}</AccordionComponent>
    );
  }
}

const AccordionComponent = ({
  labels,
  multiple,
  children,
}: PropsWithChildren<Data>): JSX.Element => {
  const type = multiple ? "multiple" : "single";
  return (
    <Accordion type={type} className="text-muted-foreground" collapsible={true}>
      {React.Children.map(children, (child, index) => {
        return (
          <AccordionItem
            key={index}
            value={index.toString()}
            className="border-muted-foreground-20"
          >
            <AccordionTrigger className="py-2 text-md">
              {renderHTML({ html: labels[index] })}
            </AccordionTrigger>
            <AccordionContent className="text-md">{child}</AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
};

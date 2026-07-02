/* Copyright 2026 Marimo. All rights reserved. */
import React, { type JSX, type PropsWithChildren } from "react";
import { z } from "zod";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { renderHTML } from "../core/RenderHTML";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  /**
   * The labels for each item; raw HTML.
   */
  labels: string[];

  /**
   * Whether to allow multiple tabs to be open.
   */
  multiple: boolean;

  /**
   * Whether to expand all items by default.
   */
  expanded: boolean;
}

export class AccordionPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-accordion";

  validator = z.object({
    labels: z.array(z.string()),
    multiple: z.boolean(),
    expanded: z.boolean().default(false),
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
  expanded,
  children,
}: PropsWithChildren<Data>): JSX.Element => {
  const type = multiple ? "multiple" : "single";
  // Build defaultValue array for expanded items
  const defaultValue = expanded
    ? labels.map((_, index) => index.toString())
    : undefined;
  return (
    <Accordion
      type={type}
      className="text-muted-foreground"
      collapsible={true}
      defaultValue={defaultValue}
    >
      {React.Children.map(children, (child, index) => {
        return (
          <AccordionItem key={index} value={index.toString()}>
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

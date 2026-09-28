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
  expanded: string[];
}

export class AccordionPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-accordion";

  validator = z.object({
    labels: z.array(z.string()),
    multiple: z.boolean(),
    expanded: z.array(z.string()).default([]),
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
  const expansionProps = multiple
    ? { type: "multiple" as const, defaultValue: expanded }
    : { type: "single" as const, defaultValue: expanded[0], collapsible: true };
  return (
    <Accordion {...expansionProps} className="text-muted-foreground">
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

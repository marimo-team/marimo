/* Copyright 2024 Marimo. All rights reserved. */
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export default {
  title: "Accordion",
  component: Accordion,
};

export const Inline = {
  render: () => (
    <Accordion type="single" collapsible={true} className="w-fit">
      <AccordionItem value="item-1" className="border-none">
        <AccordionTrigger className="data-[state=open]:underline items-center justify-start space-x-1 py-2">
          Tip
        </AccordionTrigger>
        <AccordionContent>
          Variables prefixed with an underscore are local to a cell.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),

  name: "Inline",
};

export const SingleItem = {
  render: () => (
    <Accordion type="single" collapsible={true} className="w-full">
      <AccordionItem value="item-1">
        <AccordionTrigger>Is it accessible?</AccordionTrigger>
        <AccordionContent>
          Yes. It adheres to the WAI-ARIA design pattern.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),

  name: "Single item.",
};

export const MultipleItemsSingle = {
  render: () => (
    <Accordion type="single" collapsible={true} className="w-full">
      <AccordionItem value="item-1">
        <AccordionTrigger>Is it accessible?</AccordionTrigger>
        <AccordionContent>
          Yes. It adheres to the WAI-ARIA design pattern.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-2">
        <AccordionTrigger>Is it styled?</AccordionTrigger>
        <AccordionContent>
          Yes. It comes with default styles that matches the other components'
          aesthetic.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-3">
        <AccordionTrigger>Is it animated?</AccordionTrigger>
        <AccordionContent>
          Yes. It's animated by default, but you can disable it if you prefer.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),

  name: "Multiple items, single.",
};

export const MultipleItemsMultiple = {
  render: () => (
    <Accordion type="multiple" className="w-full">
      <AccordionItem value="item-1">
        <AccordionTrigger>Is it accessible?</AccordionTrigger>
        <AccordionContent>
          Yes. It adheres to the WAI-ARIA design pattern.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-2">
        <AccordionTrigger>Is it styled?</AccordionTrigger>
        <AccordionContent>
          Yes. It comes with default styles that matches the other components'
          aesthetic.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-3">
        <AccordionTrigger>Is it animated?</AccordionTrigger>
        <AccordionContent>
          Yes. It's animated by default, but you can disable it if you prefer.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),

  name: "Multiple items, multiple.",
};

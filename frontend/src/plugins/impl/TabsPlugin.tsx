/* Copyright 2026 Marimo. All rights reserved. */
import React, { type JSX, type PropsWithChildren } from "react";
import { z } from "zod";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { cn } from "../../utils/cn";
import { renderHTML } from "../core/RenderHTML";
import type { IPlugin, IPluginProps } from "../types";
import { Labeled } from "./common/labeled";

interface Data {
  /**
   * The labels for each tab; raw HTML.
   */
  tabs: string[];
  label: string | null;
  orientation: "horizontal" | "vertical";
}

// Selected tab index
type T = string;

export class TabsPlugin implements IPlugin<T, Data> {
  tagName = "marimo-tabs";

  validator = z.object({
    tabs: z.array(z.string()),
    label: z.string().nullable(),
    orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TabComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      >
        {props.children}
      </TabComponent>
    );
  }
}

interface TabComponentProps extends Data {
  value: T;
  setValue: (value: T) => void;
}

const TabComponent = ({
  tabs,
  label,
  orientation,
  value,
  setValue,
  children,
}: PropsWithChildren<TabComponentProps>): JSX.Element => {
  // We use the index since labels are raw HTML and can't be used as keys
  // Tabs default to the first tab if the value is not set
  const [internalValue, setInternalValue] = React.useState(value || "0");

  const handleChange = (newValue: T) => {
    setInternalValue(newValue);
    setValue(newValue);
  };

  // Reset the internal value if the value is changed externally
  // and not empty
  if (value !== internalValue && !!value) {
    setInternalValue(value);
  }

  const isVertical = orientation === "vertical";
  const childArray =
    children == null ? [] : Array.isArray(children) ? children : [children];

  return (
    <Labeled label={label} align="top" fullWidth={true}>
      <Tabs
        value={internalValue}
        onValueChange={handleChange}
        orientation={orientation}
        className={cn(isVertical && "flex flex-row gap-3")}
      >
        <TabsList
          className={cn(
            "scrollbar-thin",
            isVertical
              ? "flex flex-col items-stretch justify-start h-auto max-h-none shrink-0 min-w-[10rem] overflow-y-auto"
              : "max-w-full overflow-x-auto justify-start",
          )}
        >
          {tabs.map((tab, index) => (
            <TabsTrigger
              key={index}
              value={index.toString()}
              className={cn(isVertical && "w-full justify-start")}
            >
              {renderHTML({ html: tab })}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className={cn(isVertical && "flex-1 min-w-0")}>
          {childArray.map((child, index) => (
            <TabsContent key={index} value={index.toString()}>
              {child}
            </TabsContent>
          ))}
        </div>
      </Tabs>
    </Labeled>
  );
};

/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../../components/ui/tabs";
import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { renderHTML } from "../core/RenderHTML";

interface Data {
  /**
   * The labels for each tab; raw HTML.
   */
  tabs: string[];
}

export class TabsPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-tabs";

  validator = z.object({
    tabs: z.array(z.string()),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return <TabComponent {...props.data}>{props.children}</TabComponent>;
  }
}

const TabComponent = ({
  tabs,
  children,
}: PropsWithChildren<Data>): JSX.Element => {
  return (
    <Tabs defaultValue="0">
      <TabsList>
        {tabs.map((tab, index) => (
          <TabsTrigger key={index} value={index.toString()}>
            {renderHTML({ html: tab })}
          </TabsTrigger>
        ))}
      </TabsList>
      {React.Children.map(children, (child, index) => {
        return <TabsContent value={index.toString()}>{child}</TabsContent>;
      })}
    </Tabs>
  );
};

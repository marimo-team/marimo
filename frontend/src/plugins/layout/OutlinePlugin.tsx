/* Copyright 2026 Marimo. All rights reserved. */
import { Provider, useAtomValue } from "jotai";
import type { JSX } from "react";
import { z } from "zod";
import { notebookOutline } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { OutlineList } from "../../components/editor/chrome/panels/outline/floating-outline";
import {
  findOutlineElements,
  useActiveOutline,
} from "../../components/editor/chrome/panels/outline/useActiveOutline";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  label?: string;
}

const OutlineContent: React.FC<{ label?: string }> = ({ label }) => {
  const { items } = useAtomValue(notebookOutline);
  const headerElements = findOutlineElements(items);
  const { activeHeaderId, activeOccurrences } =
    useActiveOutline(headerElements);

  if (items.length === 0) {
    return (
      <div className="text-muted-foreground text-sm p-4 border border-dashed border-border rounded-lg">
        No outline found. Add markdown headings to your notebook to create an
        outline.
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg">
      {label && (
        <div className="px-4 py-2 border-b border-border font-medium text-sm">
          {label}
        </div>
      )}
      <OutlineList
        className="max-h-[400px]"
        items={items}
        activeHeaderId={activeHeaderId}
        activeOccurrences={activeOccurrences}
      />
    </div>
  );
};

export class OutlinePlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-outline";

  validator = z.object({
    label: z.string().optional(),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    const { label } = props.data;

    return (
      <Provider store={store}>
        <OutlineContent label={label} />
      </Provider>
    );
  }
}

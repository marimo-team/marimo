/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";
import { z } from "zod";

import { UI_ELEMENT_TAG_NAME } from "../../core/dom/UIElement";
import {
  marimoValueInputEvent,
  MarimoValueInputEventType,
} from "../../core/dom/events";
import { IPlugin, IPluginProps, Setter } from "../types";

// key => value updates
type T = Record<string, unknown> | null;

interface Data {
  label: string | null;
  // mapping from elementId to key
  elementIds: Record<string, string>;
}

export class DictPlugin implements IPlugin<T, Data> {
  tagName = "marimo-dict";

  validator = z.object({
    label: z.string().nullable(),
    elementIds: z.record(z.string(), z.string()),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <Dict {...props.data} value={props.value} setValue={props.setValue}>
        {props.children}
      </Dict>
    );
  }
}

interface DictProps extends Data {
  value: T;
  setValue: Setter<T>;
  children?: React.ReactNode | undefined;
}

const Dict = ({
  elementIds,
  setValue,
  children,
}: DictProps): React.ReactNode => {
  useEffect(() => {
    // Spy on child input events to update state
    //
    // When a child fires an input event, we need to update a dict entry
    const handleUpdate = (e: MarimoValueInputEventType) => {
      const target = e.detail.element;
      if (target === null || !(target instanceof Node)) {
        return;
      }
      const node = target.parentNode;
      if (node === null || node.nodeName !== UI_ELEMENT_TAG_NAME) {
        // If something other than a UI element triggered an event, ignore it
        return;
      }
      const id = (node as Element).getAttribute("object-id") as string;
      const key = elementIds[id];
      if (key === undefined) {
        // If the UI element firing the event is not in the dict, ignore it
        return;
      }

      // Tell Python to update the dict at the given key with the new value
      setValue(() => {
        const updates: Record<string, unknown> = {};
        updates[key] = e.detail.value;
        return updates;
      });
    };
    document.addEventListener(marimoValueInputEvent, handleUpdate);
    return () => {
      document.removeEventListener(marimoValueInputEvent, handleUpdate);
    };
  }, [elementIds, setValue]);

  return children;
};

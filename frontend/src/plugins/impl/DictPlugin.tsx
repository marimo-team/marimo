/* Copyright 2024 Marimo. All rights reserved. */
import { type JSX, useEffect } from "react";
import { z } from "zod";
import {
  MarimoValueInputEvent,
  type MarimoValueInputEventType,
} from "../../core/dom/events";
import { getUIElementObjectId } from "../../core/dom/ui-element";
import type { IPlugin, IPluginProps, Setter } from "../types";

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
      const objectId = getUIElementObjectId(target);
      if (objectId === null) {
        return;
      }
      const key = elementIds[objectId];
      if (key === undefined) {
        // If the UI element firing the event is not in the dict, ignore it
        return;
      }
      // Update the dict at the given key with the new value
      setValue((prevValue) => {
        const nextValue = prevValue ? { ...prevValue } : {};
        nextValue[key] = e.detail.value;
        return nextValue;
      });
    };
    document.addEventListener(MarimoValueInputEvent.TYPE, handleUpdate);
    return () => {
      document.removeEventListener(MarimoValueInputEvent.TYPE, handleUpdate);
    };
  }, [elementIds, setValue]);

  return children;
};

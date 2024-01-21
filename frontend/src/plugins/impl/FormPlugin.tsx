/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import { z } from "zod";

import { getUIElementObjectId } from "../../core/dom/UIElement";
import {
  marimoValueInputEvent,
  MarimoValueInputEventType,
} from "@/core/dom/events";
import { IPlugin, IPluginProps, Setter } from "../types";
import { Button } from "../../components/ui/button";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { cn } from "../../utils/cn";
import { renderHTML } from "../core/RenderHTML";

type T = unknown;

interface Data {
  label: string | null;
  elementId: string;
}

/** FormPlugin
 *
 * Associates a plugin with a submit button. The associated plugin's
 * value updates are captured by this plugin; when the submit button
 * is clicked, this plugin assumes the value of the associated plugin.
 */
export class FormPlugin implements IPlugin<T, Data> {
  tagName = "marimo-form";

  validator = z.object({
    label: z.string().nullable(),
    elementId: z.string(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <Form {...props.data} value={props.value} setValue={props.setValue}>
        {props.children}
      </Form>
    );
  }
}

interface SubmitBoxProps<T> {
  children: React.ReactNode;
  currentValue: T;
  newValue: T;
  setValue: Setter<T>;
  label: string | null;
}

const SubmitBox = <T,>({
  children,
  currentValue,
  newValue,
  setValue,
  label,
}: SubmitBoxProps<T>) => {
  const synchronized = newValue === currentValue;
  const variant = synchronized ? "secondary" : "action";

  return (
    <div
      className={cn("rounded-lg border mt-2 mb-2 shadow-md", {
        "bg-[var(--gray-1)] border-input": synchronized,
        "bg-[var(--amber-1)] border-[var(--amber-7)]": !synchronized,
      })}
      onKeyDown={(evt) => {
        // Handle enter + ctrl/meta key
        if (evt.key === "Enter" && (evt.ctrlKey || evt.metaKey)) {
          evt.preventDefault();
          evt.stopPropagation();
          setValue(newValue);
        }
      }}
    >
      {label === null ? null : (
        <div className="text-center mt-4">{renderHTML({ html: label })}</div>
      )}
      <div className="pl-12 pr-12 pt-4">{children}</div>
      <div className="text-right mt-0.5 font-code p-4">
        <Button
          variant={variant}
          onClick={() => {
            setValue(newValue);
          }}
          type="submit"
        >
          Submit
        </Button>
      </div>
    </div>
  );
};

interface SubmitProps extends Data {
  value: T;
  setValue: Setter<T>;
  children?: React.ReactNode | undefined;
}

const Form = ({ elementId, value, setValue, children, label }: SubmitProps) => {
  // The internal (buffered) value is initialized as the current value of the
  // wrapped plugin; this buffered value is in contrast to the actual
  // value of the plugin, which is the value of the wrapped plugin when
  // the submit button was last clicked/activated.
  const [internalValue, setInternalValue] = useState<T>(
    UI_ELEMENT_REGISTRY.lookupValue(elementId)
  );

  // The Form may be rendered before the child plugin is, so after mount
  // we lookup the plugin once again.
  useEffect(() => {
    setInternalValue(UI_ELEMENT_REGISTRY.lookupValue(elementId));
  }, [elementId]);

  useEffect(() => {
    // Spy on when the plugin generates an event (MarimoValueInputEvent)
    const handleUpdate = (e: MarimoValueInputEventType) => {
      const target = e.detail.element;
      if (target === null || !(target instanceof Node)) {
        return;
      }
      const objectId = getUIElementObjectId(target);
      if (objectId === elementId) {
        setInternalValue(e.detail.value);
      }
    };
    document.addEventListener(marimoValueInputEvent, handleUpdate);
    return () => {
      document.removeEventListener(marimoValueInputEvent, handleUpdate);
    };
  }, [elementId, setValue]);

  return (
    <SubmitBox<T>
      currentValue={value}
      newValue={internalValue}
      setValue={setValue}
      label={label}
    >
      {children}
    </SubmitBox>
  );
};

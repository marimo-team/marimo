/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef, useState } from "react";
import { z } from "zod";

import { getUIElementObjectId, isUIElement } from "../../core/dom/UIElement";
import {
  marimoValueInputEvent,
  MarimoValueInputEventType,
} from "@/core/dom/events";
import { Setter } from "../types";
import { Button } from "../../components/ui/button";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { cn } from "../../utils/cn";
import { renderHTML } from "../core/RenderHTML";
import { Loader2Icon } from "lucide-react";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { createPlugin } from "../core/builder";
import { rpc } from "../core/rpc";
import { Banner } from "./common/error-banner";

type T = unknown;

interface Data {
  label: string | null;
  elementId: string;
  bordered: boolean;
  loading: boolean;
  submitButtonLabel: string;
  submitButtonTooltip?: string;
  submitButtonDisabled: boolean;
  clearOnSubmit: boolean;
  showClearButton: boolean;
  clearButtonLabel: string;
  clearButtonTooltip?: string;
  shouldValidate?: boolean;
}

/**
 * FormPlugin
 *
 * Associates a plugin with a submit button. The associated plugin's
 * value updates are captured by this plugin; when the submit button
 * is clicked, this plugin assumes the value of the associated plugin.
 */

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  validate: (req: { value?: unknown }) => Promise<string | undefined | null>;
};

export const FormPlugin = createPlugin("marimo-form")
  .withData<Data>(
    z.object({
      label: z.string().nullable(),
      elementId: z.string(),
      bordered: z.boolean().default(true),
      loading: z.boolean().default(false),
      submitButtonLabel: z.string().default("Submit"),
      submitButtonTooltip: z.string().optional(),
      submitButtonDisabled: z.boolean().default(false),
      clearOnSubmit: z.boolean().default(false),
      showClearButton: z.boolean().default(false),
      clearButtonLabel: z.string().default("Clear"),
      clearButtonTooltip: z.string().optional(),
      shouldValidate: z.boolean().optional(),
    }),
  )
  .withFunctions<Functions>({
    validate: rpc
      .input(z.object({ value: z.unknown() }))
      .output(z.string().nullish()),
  })
  .renderer(({ data, functions, ...rest }) => {
    return (
      <TooltipProvider>
        <Form {...data} {...rest} {...functions} />
      </TooltipProvider>
    );
  });

export interface FormWrapperProps<T>
  extends Omit<Data, "elementId">,
    Functions {
  children: React.ReactNode;
  currentValue: T;
  newValue: T;
  setValue: Setter<T>;
}

export const FormWrapper = <T,>({
  children,
  currentValue,
  newValue,
  setValue,
  label,
  bordered,
  loading,
  submitButtonLabel,
  submitButtonTooltip,
  submitButtonDisabled,
  clearOnSubmit,
  showClearButton,
  clearButtonLabel,
  clearButtonTooltip,
  validate,
  shouldValidate,
}: FormWrapperProps<T>) => {
  const formDiv = useRef<HTMLFormElement>(null);
  const synchronized = newValue === currentValue;
  const variant = synchronized ? "secondary" : "action";
  const [error, setError] = useState<string | null>(null);

  const clear = () => {
    if (formDiv.current) {
      clearInputs(formDiv.current);
    }
  };

  return (
    <form
      className="contents"
      ref={formDiv}
      onSubmit={async (evt) => {
        evt.preventDefault();

        if (shouldValidate) {
          const response = await validate({ value: newValue }).catch(
            (error_) => {
              setError(error_.message ?? "Error validating");
            },
          );
          if (response != null) {
            setError(response);
            return;
          }
        }

        setError(null);
        setValue(newValue);
        if (clearOnSubmit) {
          clear();
        }
      }}
    >
      <div
        className={cn("flex flex-col gap-4 rounded-lg py-4 px-8", {
          "bg-[var(--gray-1)] shadow-md border border-input": bordered,
          "bg-[var(--amber-1)] border-[var(--amber-7)]":
            !synchronized && bordered,
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
          <div className="text-center">{renderHTML({ html: label })}</div>
        )}
        {error != null && (
          <Banner kind="danger" className="rounded">
            {error ?? "Invalid input"}
          </Banner>
        )}
        <div>{children}</div>
        <div className="flex justify-end gap-2 font-code">
          {showClearButton &&
            withTooltip(
              <Button
                data-testid="marimo-plugin-form-clear-button"
                variant="text"
                onClick={(e) => {
                  e.preventDefault();
                  clear();
                }}
              >
                {clearButtonLabel}
              </Button>,
              clearButtonTooltip,
            )}
          {withTooltip(
            <Button
              data-testid="marimo-plugin-form-submit-button"
              variant={variant}
              disabled={submitButtonDisabled || loading}
              type="submit"
            >
              {loading && <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />}
              {submitButtonLabel}
            </Button>,
            submitButtonTooltip,
          )}
        </div>
      </div>
    </form>
  );
};

interface FormProps extends Data, Functions {
  value: T;
  setValue: Setter<T>;
  children?: React.ReactNode | undefined;
}

const Form = ({
  elementId,
  value,
  setValue,
  children,
  validate,
  ...data
}: FormProps) => {
  // The internal (buffered) value is initialized as the current value of the
  // wrapped plugin; this buffered value is in contrast to the actual
  // value of the plugin, which is the value of the wrapped plugin when
  // the submit button was last clicked/activated.
  const [internalValue, setInternalValue] = useState<T>(
    UI_ELEMENT_REGISTRY.lookupValue(elementId),
  );

  // The Form may be rendered before the child plugin is, so after mount
  // we lookup the plugin once again.
  useEffect(() => {
    setInternalValue(UI_ELEMENT_REGISTRY.lookupValue(elementId));
  }, [elementId]);

  // Edge case: the Form plugin may be re-created in Python with the same
  // wrapped `elementId`, meaning the value of the wrapped element
  // can change without the plugin generating an event
  const wrappedValue = UI_ELEMENT_REGISTRY.lookupValue(elementId);
  if (wrappedValue !== internalValue) {
    setInternalValue(wrappedValue);
  }

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
    <FormWrapper<T>
      currentValue={value}
      newValue={internalValue}
      setValue={setValue}
      validate={validate}
      {...data}
    >
      {children}
    </FormWrapper>
  );
};

function withTooltip(element: JSX.Element, tooltip?: string) {
  if (tooltip) {
    return <Tooltip content={tooltip}>{element}</Tooltip>;
  }
  return element;
}

/**
 * Traverse the input elements and find all IUIElement instances and reset them.
 */
function clearInputs(element: Element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }

  // If the element has a shadowRoot, traverse its children
  if (element.shadowRoot) {
    [...element.shadowRoot.children].forEach(clearInputs);
  }

  // Traverse the children of the element in the light DOM
  [...element.children].forEach(clearInputs);

  if (isUIElement(element)) {
    element.reset();
  }
}

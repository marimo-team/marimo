/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { SignalListeners, VegaLite, View } from "react-vega";
import { IPlugin, IPluginProps } from "@/plugins/types";
import { makeSelectable } from "./make-selectable";
import { useMemo, useRef, useState } from "react";
import { getSelectionParamNames } from "./params";
import { VegaLiteSpec } from "./types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { useDeepCompareMemoize } from "@/hooks/useDeppCompareMemoize";
import { useDebugMounting, usePropsDidChange } from "@/hooks/debug";
import { debounce } from "lodash-es";
import useEvent from "react-use-event-hook";
import { Logger } from "@/utils/Logger";

import "./vega.css";

interface Data {
  spec: VegaLiteSpec;
  selectionChart: boolean | "point" | "interval";
  selectionFields: boolean | string[];
}

interface T {
  [channel: string]: {
    // List of selected items
    vlPoint?: { or: unknown[] };
    // Either a range or a list of values
    [field: string]:
      | [number, number]
      | string[]
      | number[]
      | { or: unknown[] }
      | undefined;
  };
}

export class VegaPlugin implements IPlugin<T, Data> {
  tagName = "marimo-vega";

  validator = z.object({
    spec: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as VegaLiteSpec),
    selectionChart: z
      .union([z.boolean(), z.literal("point"), z.literal("interval")])
      .default(true),
    selectionFields: z.union([z.boolean(), z.array(z.string())]).default(true),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <VegaComponent
        value={props.value}
        setValue={props.setValue}
        {...props.data}
      />
    );
  }
}

interface VegaComponentProps<T> extends Data {
  value: T;
  setValue: (value: T) => void;
}

export const VegaComponent = ({
  value,
  setValue,
  selectionChart,
  selectionFields,
  spec,
}: VegaComponentProps<T>): JSX.Element => {
  const vegaView = useRef<View>();
  const [error, setError] = useState<Error>();

  // Debug
  useDebugMounting("VegaComponent");
  usePropsDidChange("VegaComponent", {
    value,
    setValue,
    selectionChart,
    selectionFields,
    spec,
  });

  // Aggressively memoize the spec, so Vega doesn't re-render/re-mount the component
  const selectableSpec = useMemo(() => {
    return makeSelectable(spec, {
      chartSelection: selectionChart,
      fieldSelection: selectionFields,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useDeepCompareMemoize(spec), selectionChart, selectionFields]);
  const names = useMemo(
    () => getSelectionParamNames(selectableSpec),
    [selectableSpec]
  );

  // Update the value when the selection changes
  // Keep the old value from other signals
  const handleUpdateValue = useEvent((newValue: T) => {
    setValue({ ...value, ...newValue });
  });

  const signalListeners = useMemo(
    () =>
      names.reduce((acc, name) => {
        // Debounce each signal listener, otherwise we may create expensive requests
        acc[name] = debounce((signalName, signalValue) => {
          Logger.debug("[Vega signal]", signalName, signalValue);
          handleUpdateValue({
            [signalName]: signalValue,
          });
        }, 100);
        return acc;
      }, {} as SignalListeners),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [useDeepCompareMemoize(names), setValue]
  );

  const handleError = useEvent((error) => {
    Logger.error(error);
    Logger.debug(selectableSpec);
    setError(error);
  });

  const handleNewView = useEvent((view) => {
    Logger.debug("[Vega view] created", view);
    vegaView.current = view;
    setError(undefined);
  });

  return (
    <>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>{error.message}</AlertTitle>
          <div className="text-md">{error.stack}</div>
        </Alert>
      )}
      <VegaLite
        spec={selectableSpec}
        actions={actions}
        signalListeners={signalListeners}
        onError={handleError}
        onNewView={handleNewView}
      />
    </>
  );
};

const actions = {
  source: false,
  compiled: false,
};

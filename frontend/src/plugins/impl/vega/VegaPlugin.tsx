/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import type { SignalListeners, View } from "react-vega";
import { IPlugin, IPluginProps } from "@/plugins/types";
import { makeSelectable } from "./make-selectable";
import { lazy, useMemo, useRef, useState } from "react";
import { getSelectionParamNames } from "./params";
import { VegaLiteSpec } from "./types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { useDebugMounting, usePropsDidChange } from "@/hooks/debug";
import { debounce } from "lodash-es";
import useEvent from "react-use-event-hook";
import { Logger } from "@/utils/Logger";

import { vegaLoadData } from "./loader";
import { useAsyncData } from "@/hooks/useAsyncData";
import { fixRelativeUrl } from "./fix-relative-url";

import "./vega.css";
import { useThemeForPlugin } from "@/theme/useTheme";
import { Objects } from "@/utils/objects";
import { asURL } from "@/utils/url";

interface Data {
  spec: VegaLiteSpec;
  chartSelection: boolean | "point" | "interval";
  fieldSelection: boolean | string[];
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
    chartSelection: z
      .union([z.boolean(), z.literal("point"), z.literal("interval")])
      .default(true),
    fieldSelection: z.union([z.boolean(), z.array(z.string())]).default(true),
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
  chartSelection,
  fieldSelection,
  spec,
}: VegaComponentProps<T>) => {
  const { data: resolvedSpec } = useAsyncData(async () => {
    // We try to resolve the data before passing it to Vega
    // otherwise it will try to load it internally and flicker
    // Instead we can handle the loading state ourselves,
    // and show the previous chart until the new one is ready

    if (!spec || !spec.data) {
      return spec;
    }

    if (!("url" in spec.data)) {
      return spec;
    }

    // Parse URL
    let url: URL;
    try {
      url = asURL(spec.data.url);
    } catch {
      return spec;
    }

    const data = await vegaLoadData(url.href, spec.data.format);
    return {
      ...spec,
      data: {
        name: url.pathname,
      },
      datasets: {
        ...spec.datasets,
        [url.pathname]: data,
      },
    } as VegaLiteSpec;
  }, [spec]);

  if (!resolvedSpec) {
    return null;
  }

  return (
    <LoadedVegaComponent
      value={value}
      setValue={setValue}
      chartSelection={chartSelection}
      fieldSelection={fieldSelection}
      spec={resolvedSpec}
    />
  );
};

const VegaLite = lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

const LoadedVegaComponent = ({
  value,
  setValue,
  chartSelection,
  fieldSelection,
  spec,
}: VegaComponentProps<T>): JSX.Element => {
  const { theme } = useThemeForPlugin();
  const vegaView = useRef<View>();
  const [error, setError] = useState<Error>();

  // Debug
  useDebugMounting("VegaComponent");
  usePropsDidChange("VegaComponent", {
    value,
    setValue,
    chartSelection,
    fieldSelection,
    spec,
  });

  // Aggressively memoize the spec, so Vega doesn't re-render/re-mount the component
  const selectableSpec = useMemo(() => {
    return makeSelectable(fixRelativeUrl(spec), {
      chartSelection,
      fieldSelection,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useDeepCompareMemoize(spec), chartSelection, fieldSelection]);
  const names = useMemo(
    () => getSelectionParamNames(selectableSpec),
    [selectableSpec],
  );

  // Update the value when the selection changes
  // Keep the old value from other signals
  const handleUpdateValue = useEvent((newValue: T) => {
    setValue({ ...value, ...newValue });
  });

  const signalListeners = useMemo(
    () =>
      names.reduce<SignalListeners>((acc, name) => {
        // Debounce each signal listener, otherwise we may create expensive requests
        acc[name] = debounce((signalName, signalValue) => {
          Logger.debug("[Vega signal]", signalName, signalValue);

          handleUpdateValue({
            [signalName]: Objects.mapValues(
              signalValue as object,
              convertSetToList,
            ),
          });
        }, 100);
        return acc;
      }, {}),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [useDeepCompareMemoize(names), setValue],
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
        theme={theme === "dark" ? "dark" : undefined}
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

/**
 * Convert any sets to a list before passing to the BE
 */
function convertSetToList(value: unknown): unknown {
  if (value instanceof Set) {
    return [...value];
  }
  return value;
}

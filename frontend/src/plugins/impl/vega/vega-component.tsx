/* Copyright 2026 Marimo. All rights reserved. */

import { isValid } from "date-fns";
import { debounce } from "lodash-es";
import { HelpCircleIcon } from "lucide-react";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { useVegaEmbed } from "react-vega";
import type { View } from "vega";
// @ts-expect-error vega-typings does not include formats
import { formats } from "vega-loader";
import { tooltipHandler } from "@/components/charts/tooltip";
import type { SignalListener } from "@/components/charts/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Tooltip } from "@/components/ui/tooltip";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { useTheme } from "@/theme/useTheme";
import { Events } from "@/utils/events";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { ErrorBanner } from "../common/error-banner";
import { fixRelativeUrl } from "./fix-relative-url";
import { arrow } from "./formats";
import { makeSelectable } from "./make-selectable";
import { getSelectionParamNames, ParamNames } from "./params";
import { resolveVegaSpecData } from "./resolve-data";
import type { VegaLiteSpec } from "./types";

// register arrow reader under type 'arrow'
formats("arrow", arrow);
export interface Data {
  spec: VegaLiteSpec;
  chartSelection: boolean | "point" | "interval";
  fieldSelection: boolean | string[];
  embedOptions?: Record<string, unknown>;
}

export interface VegaComponentState {
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

interface VegaComponentProps<T> extends Data {
  value: T;
  setValue: (value: T) => void;
}

const VegaComponent = ({
  value,
  setValue,
  chartSelection,
  fieldSelection,
  spec,
  embedOptions,
}: VegaComponentProps<VegaComponentState>) => {
  const { data: resolvedSpec, error } = useAsyncData(async () => {
    // We try to resolve the data before passing it to Vega
    // otherwise it will try to load it internally and flicker
    // Instead we can handle the loading state ourselves,
    // and show the previous chart until the new one is ready
    return resolveVegaSpecData(spec);
  }, [spec]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

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
      embedOptions={embedOptions}
    />
  );
};

const LoadedVegaComponent = ({
  value,
  setValue,
  chartSelection,
  fieldSelection,
  spec,
  embedOptions,
}: VegaComponentProps<VegaComponentState>): JSX.Element => {
  const { theme } = useTheme();
  const vegaRef = useRef<HTMLDivElement>(null);
  const vegaView = useRef<View>(undefined);
  const [error, setError] = useState<Error>();

  // Merge default actions with user-provided embed options
  const actions = useMemo(() => {
    // If embedOptions contains 'actions', use it directly
    if (embedOptions && "actions" in embedOptions) {
      return embedOptions.actions as
        | boolean
        | {
            export?: boolean;
            source?: boolean;
            compiled?: boolean;
            editor?: boolean;
          }
        | undefined;
    }

    // Otherwise use defaults
    return {
      source: false,
      compiled: false,
    };
  }, [embedOptions]);

  // Aggressively memoize the spec, so Vega doesn't re-render/re-mount the component
  const specMemo = useDeepCompareMemoize(spec);
  const selectableSpec = useMemo(() => {
    return makeSelectable(fixRelativeUrl(specMemo), {
      chartSelection,
      fieldSelection,
    });
  }, [specMemo, chartSelection, fieldSelection]);
  const names = useMemo(
    () => getSelectionParamNames(selectableSpec),
    [selectableSpec],
  );

  // Update the value when the selection changes
  // Keep the old value from other signals
  const handleUpdateValue = useEvent((newValue: VegaComponentState) => {
    setValue({ ...value, ...newValue });
  });

  const debouncedSignalHandler = useMemo(
    () =>
      debounce((signalName: string, signalValue: unknown) => {
        Logger.debug("[Vega signal]", signalName, signalValue);
        let result = Objects.mapValues(
          signalValue as object,
          convertDatetimeToEpochMilliseconds,
        );
        result = Objects.mapValues(result, convertSetToList);

        handleUpdateValue({
          [signalName]: result,
        });
      }, 100),
    [handleUpdateValue],
  );

  const namesMemo = useDeepCompareMemoize(names);
  const signalListeners = useMemo(
    () =>
      namesMemo.reduce<SignalListener[]>((acc, name) => {
        // pan/zoom does not count towards selection
        if (ParamNames.PAN_ZOOM === name) {
          return acc;
        }

        // bin_coloring params are used ONLY for opacity/visual feedback.
        // They should NOT send signals to the backend for filtering.
        // The regular selection params (point/interval) handle backend filtering.
        if (ParamNames.isBinColoring(name)) {
          return acc;
        }

        acc.push({
          signalName: name,
          handler: (signalName, signalValue) =>
            // Debounce the signal listener, otherwise we may create expensive requests
            debouncedSignalHandler(signalName, signalValue),
        });

        return acc;
      }, []),
    [namesMemo, debouncedSignalHandler],
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

  const renderHelpContent = () => {
    const hints: [string, string][] = [];
    if (ParamNames.hasPoint(names)) {
      hints.push([
        "Point selection",
        "click to select a point; hold shift for multi-select",
      ]);
    }

    if (ParamNames.hasInterval(names)) {
      hints.push([
        "Interval selection",
        "click and drag to select an interval",
      ]);
    }

    if (ParamNames.hasLegend(names)) {
      hints.push([
        "Legend selection",
        "click to select a legend item; hold shift for multi-select",
      ]);
    }

    if (ParamNames.hasPanZoom(names)) {
      hints.push(
        ["Pan", "hold the meta key and drag"],
        ["Zoom", "hold the meta key and scroll"],
      );
    }

    if (hints.length === 0) {
      return null;
    }

    return (
      <Tooltip
        delayDuration={300}
        side="left"
        content={
          <div className="text-xs flex flex-col">
            {hints.map((hint, i) => (
              <div key={i}>
                <span className="font-bold tracking-wide">{hint[0]}:</span>{" "}
                {hint[1]}
              </div>
            ))}
          </div>
        }
      >
        <HelpCircleIcon
          className={
            "absolute bottom-1 right-0 m-2 h-4 w-4 cursor-help text-muted-foreground hover:text-foreground"
          }
        />
      </Tooltip>
    );
  };

  const embed = useVegaEmbed({
    ref: vegaRef,
    spec: selectableSpec,
    options: {
      theme: theme === "dark" ? "dark" : undefined,
      actions: actions,
      mode: "vega-lite",
      tooltip: tooltipHandler.call,
      renderer: "canvas",
    },
    onError: handleError,
    onEmbed: handleNewView,
  });

  useEffect(() => {
    signalListeners.forEach(({ signalName, handler }) => {
      // Existing bug. TODO: Some signal listeners are invalid
      try {
        embed?.view.addSignalListener(signalName, handler);
      } catch (error) {
        Logger.error(error);
      }
    });

    return () => {
      signalListeners.forEach(({ signalName, handler }) => {
        try {
          embed?.view.removeSignalListener(signalName, handler);
        } catch (error) {
          Logger.error(error);
        }
      });
    };
  }, [embed, signalListeners]);

  return (
    <>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>{error.message}</AlertTitle>
          <div className="text-md">{error.stack}</div>
        </Alert>
      )}
      <div
        className="relative"
        // Capture the pointer down event to prevent the parent from handling it
        onPointerDown={Events.stopPropagation()}
      >
        <div ref={vegaRef} />
        {renderHelpContent()}
      </div>
    </>
  );
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

function convertDatetimeToEpochMilliseconds(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((v) => {
      if (v instanceof Date && isValid(v)) {
        return new Date(v).getTime();
      }
      return v;
    });
  }
  return value;
}

export default VegaComponent;

/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-base-to-string */
import { z } from "zod";
import "../vega/vega.css";

import * as cql from "compassql/build/src";
import { createPlugin } from "@/plugins/core/builder";
import { useAsyncData } from "@/hooks/useAsyncData";
import React, { useMemo } from "react";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { vegaLoadData } from "../vega/loader";
import { VegaLite } from "react-vega";
import { ListFilterIcon } from "lucide-react";
import { QueryForm } from "./components/query-form";
import {
  chartSpecAtom,
  relatedChartSpecsAtom,
  useChartSpecActions,
} from "./state/reducer";
import { Provider, createStore, useAtomValue } from "jotai";
import { Button } from "@/components/ui/button";
import { SpecificEncoding } from "./encoding";
import { Objects } from "@/utils/objects";
import { Badge } from "@/components/ui/badge";
import { ErrorBanner } from "../common/error-banner";
import { ColumnSummary } from "./components/column-summary";
import { VegaLiteProps } from "react-vega/lib/VegaLite";
import { useOnMount } from "@/hooks/useLifecycle";
import { ChartSpec } from "./state/types";

/**
 * @param label - a label of the table
 * @param data - the data to display
 */
interface Data {
  label?: string | null;
  data: string;
}

// Value is unused for now
type S = ChartSpec | undefined;

export const DataExplorerPlugin = createPlugin<S>("marimo-data-explorer")
  .withData(
    z.object({
      label: z.string().nullish(),
      data: z.string(),
    }),
  )
  .renderer((props) => (
    <TooltipProvider>
      <ConnectedDataExplorerComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    </TooltipProvider>
  ));

const ConnectedDataExplorerComponent = (props: DataTableProps): JSX.Element => {
  const store = useMemo(() => createStore(), []);

  useOnMount(() => {
    // Subscribe to the store
    const unsub = store.sub(chartSpecAtom, () => {
      const value = store.get(chartSpecAtom);
      const { schema, ...withoutSchema } = value;
      props.setValue(withoutSchema);
    });

    // Set the initial value
    const value = props.value;
    if (value && Object.keys(value).length > 0) {
      store.set(chartSpecAtom, value);
    }

    return unsub;
  });

  return (
    <Provider store={store}>
      <DataExplorerComponent {...props} />
    </Provider>
  );
};

interface DataTableProps extends Data {
  value: S;
  setValue: (value: S) => void;
}

const ACTIONS: VegaLiteProps["actions"] = {
  export: { svg: true, png: true },
  source: false,
  compiled: false,
  editor: false,
};
const PADDING = { left: 20, right: 20, top: 20, bottom: 20 };

export const DataExplorerComponent = ({
  data: dataUrl,
}: DataTableProps): JSX.Element => {
  const actions = useChartSpecActions();
  const { data, loading, error } = useAsyncData(async () => {
    if (!dataUrl) {
      return {};
    }
    const chartData = await vegaLoadData(dataUrl, {
      type: "csv",
      parse: "auto",
    });
    const schema = cql.schema.build(chartData);
    actions.setSchema(schema);
    return { chartData, schema };
  }, [dataUrl]);

  const { mark } = useAtomValue(chartSpecAtom);
  const charts = useAtomValue(relatedChartSpecsAtom);

  if (error) {
    return <ErrorBanner error={error} />;
  }
  if (!data) {
    return <div />;
  }
  const { chartData, schema } = data;
  if (loading || !schema) {
    return <div />;
  }

  const mainPlot = charts.main?.plots?.[0];
  const existingEncodingNames = new Set(
    mainPlot?.fieldInfos.map((info) => info.fieldDef.field),
  );

  const renderMainPlot = () => {
    if (!mainPlot) {
      return <ColumnSummary schema={schema} />;
    }

    return (
      <div className="flex overflow-y-auto justify-center items-center flex-1 w-[90%]">
        <VegaLite
          data={{ source: chartData }}
          padding={PADDING}
          actions={ACTIONS}
          spec={makeResponsive(mainPlot.spec)}
        />
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <QueryForm mark={mark} schema={schema} />
        {renderMainPlot()}
      </div>

      <HorizontalCarousel>
        {[
          charts.histograms?.plots,
          charts.addCategoricalField?.plots,
          charts.addQuantitativeField?.plots,
          charts.addTemporalField?.plots,
        ]
          .filter(Boolean)
          .flat()
          .map((plot, idx) => (
            <HorizontalCarouselItem
              key={idx}
              title={
                <div className="flex flex-row gap-1">
                  {plot.fieldInfos.map((info) => {
                    const label =
                      info.fieldDef.field === "*"
                        ? "Count"
                        : info.fieldDef.fn
                          ? `${info.fieldDef.fn}(${info.fieldDef.field})`
                          : info.fieldDef.field.toString();
                    return (
                      <Badge
                        variant={
                          existingEncodingNames.has(info.fieldDef.field)
                            ? "secondary"
                            : "defaultOutline"
                        }
                        key={label}
                      >
                        {label}
                      </Badge>
                    );
                  })}
                </div>
              }
              actions={
                <Tooltip content="Make main plot">
                  <Button
                    data-testid="marimo-plugin-data-explorer-make-main-plot"
                    variant="text"
                    size={"icon"}
                    onClick={() => {
                      const encoding: SpecificEncoding = Objects.fromEntries(
                        plot.fieldInfos.map((info) => [
                          info.channel,
                          info.fieldDef,
                        ]),
                      );
                      actions.setEncoding(encoding);
                    }}
                  >
                    <ListFilterIcon className="w-4 h-4" />
                  </Button>
                </Tooltip>
              }
            >
              <VegaLite
                data={{ source: chartData }}
                key={idx}
                actions={false}
                spec={plot.spec}
              />
            </HorizontalCarouselItem>
          ))}
      </HorizontalCarousel>
    </div>
  );
};

const HorizontalCarousel = ({
  children,
}: {
  children: React.ReactNode;
}): React.ReactNode => {
  if (React.Children.count(children) === 0) {
    return null;
  }

  return (
    <div className="flex flex-row overflow-x-auto overflow-y-hidden gap-4 snap-x pb-4">
      {children}
    </div>
  );
};

const HorizontalCarouselItem = ({
  title,
  children,
  actions,
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
}): React.ReactNode => {
  return (
    <div className="flex-shrink-0 bg-card shadow-md border overflow-hidden rounded snap-start">
      <div className="flex flex-row justify-between items-center bg-[var(--slate-3)] py-0.5 px-2">
        <div className="text-sm font-medium">{title}</div>
        {actions}
      </div>
      <div className="px-6 pt-2 max-h-[280px] overflow-y-auto">{children}</div>
    </div>
  );
};

// Make the plot responsive
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function makeResponsive(spec: any) {
  // NOTE: for row/column, this applies to the inner plot
  // so we tend to overflow due to the legends,
  // So for row/column, we skip the responsive spec
  // https://vega.github.io/vega-lite/docs/size.html#width-and-height-of-multi-view-displays
  const hasRowOrColumn = Boolean(spec.encoding?.row || spec.encoding?.column);
  if (!hasRowOrColumn) {
    spec.width = "container";
  }
  return spec;
}

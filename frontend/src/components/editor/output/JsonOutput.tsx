/* Copyright 2026 Marimo. All rights reserved. */
import JsonView from "@uiw/react-json-view";
import {
  type ComponentProps,
  memo,
  useCallback,
  useMemo,
  useState,
} from "react";
import { useEvent } from "@/hooks/useEvent";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { CopyClipboardIcon } from "../../icons/copy-icon";
import { getCopyValue } from "./json-output/formatting";
import {
  determineMaxDisplayLength,
  PAGE_SIZE,
  paginateJson,
  shouldExpandNode,
} from "./json-output/pagination";
import {
  COLLAPSED_TEXT_LENGTH,
  JSON_NULL_RENDER,
  PYTHON_FALSE_RENDER,
  PYTHON_NULL_RENDER,
  PYTHON_TRUE_RENDER,
  renderArrow,
  renderKeyName,
  renderKeyQuote,
  renderStringValue,
} from "./json-output/renderers";
import { marimoDarkTheme, marimoLightTheme } from "./json-output/themes";

interface Props {
  data: unknown;
  format?: "auto" | "tree" | "raw";
  /** If false, omit the root label. */
  name?: string | false;
  className?: string;
  /** Python mode decodes MIME leaves and uses True/False/None. */
  valueTypes?: "json" | "python";
}

export const JsonOutput = memo(function JsonOutput({
  data,
  format = "auto",
  ...props
}: Props) {
  if (format === "raw" || data === null || typeof data !== "object") {
    return (
      <pre className={props.className}>{JSON.stringify(data, null, 2)}</pre>
    );
  }
  return <JsonTree {...props} data={data} />;
});

type TreeProps = Omit<Props, "data" | "format"> & { data: object };
type RowRenderer = NonNullable<
  ComponentProps<typeof JsonView.Row<"div">>["render"]
>;
type CountRenderer = NonNullable<
  ComponentProps<typeof JsonView.CountInfo<"span">>["render"]
>;

function JsonTree({
  data,
  name = false,
  valueTypes = "python",
  className,
}: TreeProps) {
  const { theme } = useTheme();
  const isPython = valueTypes === "python";
  const pageSize = determineMaxDisplayLength(data) ?? PAGE_SIZE;
  const [pagination, setPagination] = useState<{
    data: object;
    limits: Record<string, number>;
  }>({ data, limits: {} });
  if (pagination.data !== data) {
    setPagination({ data, limits: {} });
  }
  const { limits } = pagination;
  const tree = useMemo(
    () => paginateJson(data, { limits, pageSize }),
    [data, limits, pageSize],
  );
  const showMore = useEvent((path: string) => {
    setPagination((prev) => ({
      ...prev,
      limits: {
        ...prev.limits,
        [path]: (prev.limits[path] ?? pageSize) + pageSize,
      },
    }));
  });

  // Render callbacks need current render state; useEvent reads committed state.
  const renderCopyButton = useCallback(
    (value: unknown) => {
      if (
        isPython &&
        typeof value === "string" &&
        /^(text\/html:|image\/|video\/)/.test(value)
      ) {
        return null;
      }
      return (
        <CopyClipboardIcon
          value={() =>
            isPython
              ? getCopyValue(tree.getOriginal(value))
              : JSON.stringify(tree.getOriginal(value), null, 2)
          }
          tooltip={false}
          buttonClassName="inline-flex ml-2 copy-button rounded w-6 h-3 justify-center items-center relative"
          className="w-5 h-5 absolute -top-0.5 p-1 hover:bg-muted rounded"
        />
      );
    },
    [isPython, tree],
  );

  const renderString = useCallback(
    (
      props: Record<string, unknown>,
      result: { type: string; value?: unknown },
    ) => renderStringValue(props, result, valueTypes),
    [valueTypes],
  );
  const renderRow = useCallback<RowRenderer>(
    (props, { value }) => {
      const page = tree.getPage(value);
      return (
        <div {...props}>
          {page ? (
            <button
              type="button"
              className="cursor-pointer text-link hover:underline"
              onClick={(event) => {
                event.stopPropagation();
                showMore(page.path);
              }}
            >
              ... {page.remaining} more items
            </button>
          ) : (
            <>
              {props.children}
              {renderCopyButton(value)}
            </>
          )}
        </div>
      );
    },
    [tree, showMore, renderCopyButton],
  );
  const renderCount = useCallback<CountRenderer>(
    (props, { value }) => {
      const original = tree.getOriginal(value);
      const count = Array.isArray(original)
        ? original.length
        : original && typeof original === "object"
          ? Object.keys(original).length
          : 0;
      return (
        <span {...props}>
          {count} {count === 1 ? "Item" : "Items"}
        </span>
      );
    },
    [tree],
  );
  const renderContainerCopy = useCallback(
    (_props: Record<string, unknown>, { value }: { value?: unknown }) =>
      renderCopyButton(value),
    [renderCopyButton],
  );

  return (
    <JsonView
      className={cn("marimo-json-output", className)}
      keyName={name || undefined}
      value={tree.data}
      style={theme === "dark" ? marimoDarkTheme : marimoLightTheme}
      displayDataTypes={false}
      enableClipboard={false}
      highlightUpdates={false}
      shortenTextAfterLength={COLLAPSED_TEXT_LENGTH}
      collapsed={false}
      shouldExpandNodeInitially={shouldExpandNode}
    >
      <JsonView.String render={renderString} />
      <JsonView.Colon style={{ marginRight: 4 }} />
      <JsonView.Arrow render={renderArrow} />
      <JsonView.CountInfo<"span"> render={renderCount} />
      <JsonView.KeyName render={isPython ? renderKeyName : undefined} />
      <JsonView.Quote render={isPython ? renderKeyQuote : undefined} />
      <JsonView.True render={isPython ? PYTHON_TRUE_RENDER : undefined} />
      <JsonView.False render={isPython ? PYTHON_FALSE_RENDER : undefined} />
      <JsonView.Null
        render={isPython ? PYTHON_NULL_RENDER : JSON_NULL_RENDER}
      />
      <JsonView.Row<"div"> render={renderRow} />
      <JsonView.CountInfoExtra render={renderContainerCopy} />
    </JsonView>
  );
}

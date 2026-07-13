/* Copyright 2026 Marimo. All rights reserved. */

import { Provider, useAtomValue } from "jotai";
import { DatabaseZapIcon } from "lucide-react";
import type React from "react";
import { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useLocale } from "react-aria";
import { ProtocolIcon } from "@/components/storage/components";
import { Badge } from "@/components/ui/badge";
import { cacheInfoAtom } from "@/core/cache/requests";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import type { ConnectionName } from "@/core/datasets/engines";
import { datasetTablesAtom } from "@/core/datasets/state";
import { getRequestClient } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { storageNamespacesAtom } from "@/core/storage/state";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { formatTime } from "@/utils/formatting";
import { prettyNumber } from "@/utils/numbers";
import {
  CONTAINER_STYLES,
  MetadataRow,
  renderDatasourceInfo,
  renderEmptyInfo,
  renderTableInfo,
  SectionHeader,
} from "../language/languages/sql/renderers";
import type { CodeLensSpec } from "./entities";

/**
 * Mounts the hover popover for a code lens into `dom`; returns a dispose
 * function.
 */
export function mountLensPopover(
  dom: HTMLElement,
  spec: CodeLensSpec,
): () => void {
  const root = createRoot(dom);
  root.render(
    <Provider store={store}>
      <LensPopover spec={spec} />
    </Provider>,
  );
  // Defer so tearing the tooltip down from inside a React event (e.g. the
  // icon's click handler) doesn't unmount mid-render
  return () => queueMicrotask(() => root.unmount());
}

const LensPopover: React.FC<{ spec: CodeLensSpec }> = ({ spec }) => {
  switch (spec.kind) {
    case "table":
      return <TablePopover name={spec.name} />;
    case "connection":
      return <ConnectionPopover name={spec.name} />;
    case "bucket":
      return <BucketPopover name={spec.name} />;
    case "cache":
      return (
        <CachePopover
          boundName={spec.cache?.boundName ?? null}
          cacheName={spec.cache?.cacheName ?? null}
        />
      );
  }
};

const TablePopover: React.FC<{ name: string }> = ({ name }) => {
  const tables = useAtomValue(datasetTablesAtom);
  const table = tables.find((t) => t.variable_name === name);
  return <>{table ? renderTableInfo(table) : renderEmptyInfo("table")}</>;
};

const ConnectionPopover: React.FC<{ name: string }> = ({ name }) => {
  const connections = useAtomValue(dataConnectionsMapAtom);
  const connection = connections.get(name as ConnectionName);
  return (
    <>
      {connection
        ? renderDatasourceInfo(connection)
        : renderEmptyInfo("database")}
    </>
  );
};

const BucketPopover: React.FC<{ name: string }> = ({ name }) => {
  const namespaces = useAtomValue(storageNamespacesAtom);
  const namespace = namespaces.find((ns) => ns.name === name);
  if (!namespace) {
    return (
      <div className={CONTAINER_STYLES}>
        <span className="text-xs text-(--slate-11)">
          No storage information available.
        </span>
      </div>
    );
  }
  return (
    <div className={CONTAINER_STYLES}>
      <SectionHeader
        icon={
          <ProtocolIcon protocol={namespace.protocol} className="w-4 h-4" />
        }
        title={namespace.displayName}
        badge={
          <Badge variant="outline" className="text-xs">
            {namespace.protocol}
          </Badge>
        }
      />
      <div className="flex flex-col gap-2 py-2">
        <MetadataRow
          label="Variable"
          value={
            <code className="text-xs bg-(--slate-4) px-1 rounded">
              {namespace.name}
            </code>
          }
        />
        <MetadataRow
          label="Root"
          value={
            <code className="text-xs bg-(--slate-4) px-1 rounded">
              {namespace.rootPath || "(root)"}
            </code>
          }
        />
        <MetadataRow
          label="Backend"
          value={<span className="font-medium">{namespace.backendType}</span>}
        />
      </div>
    </div>
  );
};

// `_cache_call.__repr__` starts with "hits=N misses=N", which survives the
// variable-preview truncation
const CACHE_STATS_PATTERN = /\bhits=(\d+) misses=(\d+)/;

const CachePopover: React.FC<{
  boundName: string | null;
  cacheName: string | null;
}> = ({ boundName, cacheName }) => {
  const { locale } = useLocale();
  const variables = useAtomValue(variablesAtom);
  const cacheInfo = useAtomValue(cacheInfoAtom);

  // Refresh notebook-wide cache info while open
  useEffect(() => {
    void getRequestClient().getCacheInfo();
  }, []);

  const variable = boundName ? variables[boundName as VariableName] : undefined;
  const stats = variable?.dataType?.startsWith("_cache_call")
    ? variable.value?.match(CACHE_STATS_PATTERN)
    : undefined;

  return (
    <div className={CONTAINER_STYLES}>
      <SectionHeader
        icon={<DatabaseZapIcon className="w-4 h-4 text-(--amber-9)" />}
        title={cacheName ?? boundName ?? "Cache"}
      />
      {stats ? (
        <div className="flex flex-col gap-2 py-2">
          <MetadataRow
            label="Hits"
            value={
              <span className="font-medium">
                {prettyNumber(Number(stats[1]), locale)}
              </span>
            }
          />
          <MetadataRow
            label="Misses"
            value={
              <span className="font-medium">
                {prettyNumber(Number(stats[2]), locale)}
              </span>
            }
          />
        </div>
      ) : (
        cacheInfo && (
          <div className="flex flex-col gap-2 py-2">
            <span className="text-xs font-medium text-(--slate-11)">
              Notebook-wide
            </span>
            <MetadataRow
              label="Hits"
              value={prettyNumber(cacheInfo.hits, locale)}
            />
            <MetadataRow
              label="Misses"
              value={prettyNumber(cacheInfo.misses, locale)}
            />
            <MetadataRow
              label="Time saved"
              value={formatTime(cacheInfo.time, locale)}
            />
          </div>
        )
      )}
      <div className="pt-2 text-xs text-(--slate-10)">
        Click to open the cache panel
      </div>
    </div>
  );
};

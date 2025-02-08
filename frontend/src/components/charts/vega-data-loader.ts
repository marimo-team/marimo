/* Copyright 2024 Marimo. All rights reserved. */
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { resolveVegaSpecData } from "@/plugins/impl/vega/resolve-data";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

interface VegaSpecResolverProps {
  spec: VegaLiteSpec;
  children: (spec: VegaLiteSpec) => React.ReactNode;
}

export const VegaSpecResolver: React.FC<VegaSpecResolverProps> = ({
  spec,
  children,
}) => {
  const specMemo = useDeepCompareMemoize(spec);
  const { data: resolvedSpec } = useAsyncData(async () => {
    return await resolveVegaSpecData(specMemo);
  }, [specMemo]);

  if (!resolvedSpec) {
    return null;
  }

  return children(resolvedSpec);
};

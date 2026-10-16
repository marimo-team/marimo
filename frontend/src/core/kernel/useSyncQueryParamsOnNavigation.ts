/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect } from "react";
import { useRequestClient } from "../network/requests";
import { syncQueryParamsOnNavigation } from "./queryParamSync";

/**
 * Report browser back/forward navigation to the kernel so cells that read
 * `mo.query_params()` re-run with the restored URL's params.
 */
export function useSyncQueryParamsOnNavigation(): void {
  const { sendUpdateQueryParams } = useRequestClient();
  useEffect(
    () => syncQueryParamsOnNavigation(sendUpdateQueryParams),
    [sendUpdateQueryParams],
  );
}

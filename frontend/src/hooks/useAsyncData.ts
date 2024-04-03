/* Copyright 2024 Marimo. All rights reserved. */
import { SetStateAction } from "jotai";
import { DependencyList, useState, useEffect, Dispatch } from "react";

interface AsyncDataResponse<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | undefined;
  setData: Dispatch<SetStateAction<T | undefined>>;
}

interface Context {
  previous(): void;
}

/**
 * A hook that loads data asynchronously.
 * Handles loading and error states, and prevents race conditions.
 */
export function useAsyncData<T>(
  loader: (context: Context) => Promise<T>,
  deps: DependencyList,
): AsyncDataResponse<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | undefined>(undefined);

  useEffect(() => {
    let isCancelled = false;
    let keepPrevious = false;
    const context = {
      previous: () => {
        keepPrevious = true;
      },
    };
    setLoading(true);
    loader(context)
      .then((data) => {
        if (isCancelled) {
          return;
        }
        if (keepPrevious) {
          return;
        }
        setData(data);
        setError(undefined);
      })
      .catch((error_) => {
        if (isCancelled) {
          return;
        }
        setError(error_);
      })
      .finally(() => {
        if (isCancelled) {
          return;
        }
        setLoading(false);
      });

    return () => {
      isCancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, setData };
}

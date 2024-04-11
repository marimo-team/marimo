/* Copyright 2024 Marimo. All rights reserved. */
import { SetStateAction } from "jotai";
import { DependencyList, useState, useEffect, Dispatch } from "react";

interface AsyncDataResponse<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | undefined;
  setData: Dispatch<SetStateAction<T | undefined>>;
}

export function combineAsyncData<T, U>(
  a: AsyncDataResponse<T>,
  b: AsyncDataResponse<U>,
): Omit<AsyncDataResponse<[T, U]>, "setData"> {
  return {
    data:
      a.data === undefined || b.data === undefined
        ? undefined
        : [a.data, b.data],
    loading: a.loading || b.loading,
    error: a.error || b.error,
  };
}

interface Context {
  previous(): void;
}

type Props<T> =
  | {
      fetch: (context: Context) => Promise<T>;
    }
  | ((context: Context) => Promise<T>);

/**
 * A hook that loads data asynchronously.
 * Handles loading and error states, and prevents race conditions.
 */
export function useAsyncData<T>(
  loaderOrProps: Props<T>,
  deps: DependencyList,
): AsyncDataResponse<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | undefined>(undefined);

  const asProps =
    typeof loaderOrProps === "function"
      ? { fetch: loaderOrProps }
      : loaderOrProps;

  useEffect(() => {
    let isCancelled = false;
    let keepPrevious = false;
    const context = {
      previous: () => {
        keepPrevious = true;
      },
    };
    setLoading(true);
    asProps
      .fetch(context)
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

/* Copyright 2024 Marimo. All rights reserved. */
import type { SetStateAction } from "jotai";
import { type DependencyList, useState, useEffect, type Dispatch } from "react";
import useEvent from "react-use-event-hook";

interface AsyncDataResponse<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | undefined;
  setData: Dispatch<SetStateAction<T | undefined>>;
  reload: () => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function combineAsyncData<T extends any[]>(
  ...responses: { [K in keyof T]: AsyncDataResponse<T[K]> }
): Omit<AsyncDataResponse<T>, "setData"> {
  return {
    data: responses.every((response) => response.data !== undefined)
      ? (responses.map((response) => response.data) as T)
      : undefined,
    loading: responses.some((response) => response.loading),
    error:
      responses.find((response) => response.error !== null)?.error || undefined,
    reload: () => {
      responses.forEach((response) => response.reload());
    },
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
  const [nonce, setNonce] = useState(0);

  const asProps =
    typeof loaderOrProps === "function"
      ? { fetch: loaderOrProps }
      : loaderOrProps;

  const fetchStable = useEvent(asProps.fetch);

  useEffect(() => {
    let isCancelled = false;
    let keepPrevious = false;
    const context = {
      previous: () => {
        keepPrevious = true;
      },
    };
    setLoading(true);
    fetchStable(context)
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
  }, [...deps, nonce, fetchStable]);

  return {
    data,
    loading,
    error,
    setData,
    reload: () => setNonce(nonce + 1),
  };
}

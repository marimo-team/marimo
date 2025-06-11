/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import {
  type DependencyList,
  type Dispatch,
  type SetStateAction,
  useState,
  useEffect,
} from "react";
import useEvent from "react-use-event-hook";

interface LoadingResponse {
  loading: true;
  data: undefined;
  error: undefined;
}

interface ErrorResponse {
  loading: false;
  data: undefined;
  error: Error;
}

interface SuccessResponse<T> {
  loading: false;
  data: T;
  error: undefined;
}

function isSuccess<T>(
  x: LoadingResponse | ErrorResponse | SuccessResponse<T>,
): x is SuccessResponse<T> {
  return !x.loading && x.error === undefined;
}

function isError(
  x: LoadingResponse | ErrorResponse | SuccessResponse<unknown>,
): x is ErrorResponse {
  return !x.loading && x.data === undefined;
}

export type AsyncDataResponse<T> =
  | LoadingResponse
  | ErrorResponse
  | SuccessResponse<T>;

export function combineAsyncData<T extends unknown[]>(
  ...responses: {
    [K in keyof T]: AsyncDataResponse<T[K]> & { reload: () => void };
  }
): AsyncDataResponse<T> & { reload: () => void } {
  invariant(
    responses.length > 0,
    "combineAsyncData requires at least one response",
  );

  const reload = () => {
    responses.forEach((response) => response.reload());
  };

  // short circuit if any response has an error
  const maybeErrorResponse = responses.find(isError);
  if (maybeErrorResponse?.error) {
    return {
      loading: false,
      data: undefined,
      error: maybeErrorResponse.error,
      reload,
    };
  }

  // Combine response data when all are successful
  if (responses.every(isSuccess)) {
    return {
      loading: false,
      data: responses.map((response) => response.data) as T,
      error: undefined,
      reload,
    };
  }

  // otherwise, we are still "loading"
  return {
    loading: true,
    data: undefined,
    error: undefined,
    reload,
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
): AsyncDataResponse<T> & {
  setData: Dispatch<SetStateAction<T>>;
  reload: () => void;
} {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<
    LoadingResponse | ErrorResponse | SuccessResponse<T>
  >({ loading: true, data: undefined, error: undefined });

  const asProps =
    typeof loaderOrProps === "function"
      ? { fetch: loaderOrProps }
      : loaderOrProps;

  const fetchStable = useEvent(asProps.fetch);

  useEffect(() => {
    const controller = new AbortController();
    let keepPrevious = false;
    const context = {
      previous: () => {
        keepPrevious = true;
      },
    };
    setResult({ loading: true, data: undefined, error: undefined });
    fetchStable(context)
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        if (keepPrevious) {
          return;
        }
        setResult({ data, error: undefined, loading: false });
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }
        setResult({ data: undefined, error, loading: false });
      });

    return () => {
      controller.abort();
    };
  }, [...deps, nonce, fetchStable]);

  return {
    ...result,
    setData: (update) => {
      let data: T;
      if (typeof update === "function") {
        invariant(isSuccess(result), "No previous state value.");
        // @ts-expect-error - TS can't narrow the type correctly
        data = update(result.data);
      } else {
        data = update;
      }
      setResult({ data, error: undefined, loading: false });
    },
    reload: () => setNonce(nonce + 1),
  };
}

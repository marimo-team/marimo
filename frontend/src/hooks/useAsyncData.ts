/* Copyright 2024 Marimo. All rights reserved. */

/**
 * @deprecated Consider using @tanstack/react-query's useQuery instead for new code.
 * React Query provides better caching, background updates, and mutation management.
 */
import {
  type DependencyList,
  type Dispatch,
  type SetStateAction,
  useEffect,
  useState,
} from "react";
import useEvent from "react-use-event-hook";
import { invariant } from "@/utils/invariant";

interface PendingResult {
  status: "pending";
  data: undefined;
  error: undefined;
  isPending: true;
  isFetching: true;
}

interface LoadingResult<T> {
  status: "loading";
  data: T;
  error: undefined;
  isPending: false;
  isFetching: true;
}

interface ErrorResult<T> {
  status: "error";
  data: undefined | T;
  error: Error;
  isPending: false;
  isFetching: false;
}

interface SuccessResult<T> {
  status: "success";
  data: T;
  error: undefined;
  isPending: false;
  isFetching: false;
}

const Result = {
  error<T>(e: Error, staleData?: T): ErrorResult<T> {
    return {
      status: "error",
      data: staleData,
      error: e,
      isPending: false,
      isFetching: false,
    };
  },
  success<T>(data: T): SuccessResult<T> {
    return {
      status: "success",
      data,
      error: undefined,
      isPending: false,
      isFetching: false,
    };
  },
  loading<T>(data: T): LoadingResult<T> {
    return {
      status: "loading",
      data,
      error: undefined,
      isPending: false,
      isFetching: true,
    };
  },
  pending(): PendingResult {
    return {
      status: "pending",
      data: undefined,
      error: undefined,
      isPending: true,
      isFetching: true,
    };
  },
};

export type AsyncDataResult<T> =
  | PendingResult
  | LoadingResult<T>
  | ErrorResult<T>
  | SuccessResult<T>;

export function combineAsyncData<T extends unknown[]>(
  ...responses: {
    [K in keyof T]: AsyncDataResult<T[K]> & { refetch: () => void };
  }
): AsyncDataResult<T> & { refetch: () => void } {
  invariant(
    responses.length > 0,
    "combineAsyncData requires at least one response",
  );

  const refetch = () => {
    responses.forEach((response) => response.refetch());
  };

  // short circuit if any response has an error
  const maybeErrorResponse = responses.find((x) => x.status === "error");
  if (maybeErrorResponse?.error) {
    return { ...Result.error(maybeErrorResponse.error), refetch };
  }

  // Combine response data when all are successful
  if (responses.every((x) => x.status === "success")) {
    return {
      ...Result.success(responses.map((response) => response.data) as T),
      refetch,
    };
  }

  const hasLoadingResponse = responses.some(
    (response) => response.status === "loading",
  );
  const allHaveData = responses.every(
    (response) => response.data !== undefined,
  );

  if (hasLoadingResponse && allHaveData) {
    return {
      ...Result.loading(responses.map((response) => response.data) as T),
      refetch,
    };
  }

  // Otherwise, we are still "pending" (initial load)
  return { ...Result.pending(), refetch };
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
): AsyncDataResult<T> & {
  setData: Dispatch<SetStateAction<T>>;
  refetch: () => void;
} {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<
    PendingResult | LoadingResult<T> | ErrorResult<T> | SuccessResult<T>
  >(Result.pending());

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
    setResult((prevResult) => {
      // If we have previous data, show reloading state
      if (prevResult.status === "success") {
        return Result.loading(prevResult.data);
      }
      // Otherwise, show initial loading state
      return Result.pending();
    });
    fetchStable(context)
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        if (keepPrevious) {
          return;
        }
        setResult(Result.success(data));
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }
        // Carry over the previous data (if any)
        setResult((prev) => Result.error(error, prev.data));
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
        invariant(
          result.status === "success" || result.status === "loading",
          "No previous state value.",
        );
        // @ts-expect-error - TS can't narrow the type correctly
        data = update(result.data);
      } else {
        data = update;
      }
      // Always transition to success state - manual updates complete the loading
      setResult(Result.success(data));
    },
    refetch: () => setNonce(nonce + 1),
  };
}

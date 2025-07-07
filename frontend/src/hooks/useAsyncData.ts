/* Copyright 2024 Marimo. All rights reserved. */
import {
  type DependencyList,
  type Dispatch,
  type SetStateAction,
  useEffect,
  useState,
} from "react";
import useEvent from "react-use-event-hook";
import { invariant } from "@/utils/invariant";

/**
 * Base result interface containing common properties for all async data states.
 *
 * @template T - The type of data being fetched
 */
interface AsyncBaseResult<T> {
  /**
   * The current status of the async operation.
   * - `pending`: Initial state, no data has been fetched yet
   * - `loading`: Data is being refetched (has previous data)
   * - `error`: The fetch operation failed
   * - `success`: Data has been successfully fetched
   */
  status: "pending" | "loading" | "error" | "success";

  /**
   * The data returned from the fetch operation.
   * - `undefined` when pending or on error (unless stale data is preserved)
   * - Contains the fetched data when successful or loading
   */
  data: T | undefined;

  /**
   * The error object if the fetch operation failed.
   * - `undefined` when not in error state
   * - Contains the Error object when fetch fails
   */
  error: Error | undefined;

  /**
   * A derived boolean indicating if this is the initial fetch.
   * - `true` when no data has been fetched yet (pending state)
   * - `false` when data has been fetched at least once
   */
  isPending: boolean;

  /**
   * A derived boolean indicating if a fetch operation is currently in progress.
   * - `true` when actively fetching data (pending or loading states)
   * - `false` when not fetching (success or error states)
   */
  isFetching: boolean;
}

/**
 * Represents the initial state when no data has been fetched yet.
 */
interface PendingResult<T> extends AsyncBaseResult<T> {
  status: "pending";
  data: undefined;
  error: undefined;
  isPending: true;
  isFetching: true;
}

/**
 * Represents the state when data is being refetched (has previous data).
 */
interface LoadingResult<T> extends AsyncBaseResult<T> {
  status: "loading";
  data: T;
  error: undefined;
  isPending: false;
  isFetching: true;
}

/**
 * Represents the error state when data fetching fails.
 */
interface ErrorResult<T> extends AsyncBaseResult<T> {
  status: "error";
  data: undefined | T;
  error: Error;
  isPending: false;
  isFetching: false;
}

/**
 * Represents the success state when data has been successfully fetched.
 */
interface SuccessResult<T> extends AsyncBaseResult<T> {
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
  pending<T>(): PendingResult<T> {
    return {
      status: "pending",
      data: undefined,
      error: undefined,
      isPending: true,
      isFetching: true,
    };
  },
};

/**
 * Union type representing all possible async data states.
 *
 * @template T - The type of data being fetched
 */
export type AsyncDataResult<T> =
  | PendingResult<T>
  | LoadingResult<T>
  | ErrorResult<T>
  | SuccessResult<T>;

/**
 * Combines multiple async data results into a single result.
 *
 * This utility function allows you to wait for multiple async operations to complete
 * and provides a unified loading/error/success state. It will:
 * - Return an error if any of the responses has an error
 * - Return success when all responses are successful
 * - Return loading when some responses are loading but all have data
 * - Return pending when any response is still pending
 *
 * @param responses - Array of async data results with refetch functions
 * @returns Combined async data result with refetch function
 *
 * @example
 * ```tsx
 * const user = useAsyncData(fetchUser, [userId]);
 * const posts = useAsyncData(fetchPosts, [userId]);
 * const combined = combineAsyncData(user, posts);
 *
 * if (combined.status === "success") {
 *   const [userData, postsData] = combined.data;
 *   // Both user and posts are loaded
 * }
 * ```
 */
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

/**
 * Context object passed to the fetch function.
 * Provides utilities for controlling the fetch behavior.
 */
interface Context {
  /**
   * Call this function to keep the previous data instead of updating.
   * Useful for conditional updates or when you want to abort the update.
   */
  previous(): void;
}

type Props<T> =
  | {
      fetch: (context: Context) => Promise<T>;
    }
  | ((context: Context) => Promise<T>);

/**
 * A hook that loads data asynchronously with proper loading states and race condition handling.
 *
 * This hook provides a comprehensive solution for async data fetching with:
 * - Proper loading states (pending, loading, success, error)
 * - Race condition prevention using AbortController
 * - Stale data handling (previous data preserved on error)
 * - Manual data updates via setData
 * - Refetch functionality
 *
 * The hook distinguishes between "pending" (initial load) and "loading" (refetch with existing data).
 *
 * @param loaderOrProps - Either a fetch function or an object with a fetch function
 * @param deps - Dependency array that triggers refetch when changed (like useEffect)
 * @returns Object with data, loading states, and control functions
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { data, status, error, refetch } = useAsyncData(
 *   async () => {
 *     const response = await fetch('/api/users');
 *     return response.json();
 *   },
 *   [] // No dependencies - fetch once
 * );
 *
 * // With dependencies
 * const { data, status, isPending, isFetching } = useAsyncData(
 *   async () => fetchUser(userId),
 *   [userId] // Refetch when userId changes
 * );
 *
 * // With context for conditional updates
 * const { data, setData } = useAsyncData(
 *   async (context) => {
 *     const newData = await fetchData();
 *     if (shouldKeepOldData(newData)) {
 *       context.previous(); // Keep previous data
 *       return;
 *     }
 *     return newData;
 *   },
 *   [someDependency]
 * );
 *
 * // Manual data updates
 * const { data, setData } = useAsyncData(fetchData, []);
 * setData(newData); // Update data manually
 * setData(prevData => ({ ...prevData, updated: true })); // Update with function
 * ```
 *
 * @example
 * ```tsx
 * // Handling different states
 * const { data, status, error, isPending, isFetching } = useAsyncData(fetchData, []);
 *
 * if (isPending) {
 *   return <div>Loading...</div>;
 * }
 *
 * if (status === "error") {
 *   return <div>Error: {error.message}</div>;
 * }
 *
 * if (status === "loading") {
 *   return <div>Previous data: {data}, Refreshing...</div>;
 * }
 *
 * if (status === "success") {
 *   return <div>Data: {JSON.stringify(data)}</div>;
 * }
 * ```
 */
export function useAsyncData<T>(
  loaderOrProps: Props<T>,
  deps: DependencyList,
): AsyncDataResult<T> & {
  /** Manually update the data. Transitions to success state. */
  setData: Dispatch<SetStateAction<T>>;
  /** Refetch the data. Increments internal nonce to trigger effect. */
  refetch: () => void;
} {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<
    PendingResult<T> | LoadingResult<T> | ErrorResult<T> | SuccessResult<T>
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

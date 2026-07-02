/* Copyright 2026 Marimo. All rights reserved. */
import * as React from "react";

import type { ToastActionElement, ToastProps } from "@/components/ui/toast";

const TOAST_LIMIT = 1;
const TOAST_REMOVE_DELAY = 10_000; // 10 seconds

type ToasterToast = Omit<ToastProps, "title"> & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: ToastActionElement;
};

const actionTypes = {
  ADD_TOAST: "ADD_TOAST",
  UPDATE_TOAST: "UPDATE_TOAST",
  DISMISS_TOAST: "DISMISS_TOAST",
  REMOVE_TOAST: "REMOVE_TOAST",
  UPSERT_TOAST: "UPSERT_TOAST",
} as const;

let count = 0;

function genId() {
  count = (count + 1) % Number.MAX_VALUE;
  return count.toString();
}

type ActionType = typeof actionTypes;

type Action =
  | {
      type: ActionType["ADD_TOAST"];
      toast: ToasterToast;
    }
  | {
      type: ActionType["UPDATE_TOAST"];
      toast: Partial<ToasterToast>;
    }
  | {
      type: ActionType["DISMISS_TOAST"];
      toastId?: ToasterToast["id"];
    }
  | {
      type: ActionType["REMOVE_TOAST"];
      toastId?: ToasterToast["id"];
    }
  | {
      type: ActionType["UPSERT_TOAST"];
      toast: ToasterToast;
    };

interface State {
  toasts: ToasterToast[];
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

// Keys of toasts requested with `once: true`, suppressed after first show
// for the lifetime of the page (i.e. one static-preview session).
const shownOnceKeys = new Set<string>();

const addToRemoveQueue = (toastId: string) => {
  if (toastTimeouts.has(toastId)) {
    return;
  }

  const timeout = setTimeout(() => {
    toastTimeouts.delete(toastId);
    dispatch({
      type: "REMOVE_TOAST",
      toastId: toastId,
    });
  }, TOAST_REMOVE_DELAY);

  toastTimeouts.set(toastId, timeout);
};

export const reducer = (state: State, action: Action): State => {
  switch (action.type) {
    case "ADD_TOAST":
      return {
        ...state,
        toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
      };

    case "UPDATE_TOAST":
      return {
        ...state,
        toasts: state.toasts.map((t) =>
          t.id === action.toast.id ? { ...t, ...action.toast } : t,
        ),
      };

    case "DISMISS_TOAST": {
      const { toastId } = action;

      // ! Side effects ! - This could be extracted into a dismissToast() action,
      // but I'll keep it here for simplicity
      if (toastId) {
        addToRemoveQueue(toastId);
      } else {
        state.toasts.forEach((toast) => {
          addToRemoveQueue(toast.id);
        });
      }

      return {
        ...state,
        toasts: state.toasts.map((t) =>
          t.id === toastId || toastId === undefined
            ? {
                ...t,
                open: false,
              }
            : t,
        ),
      };
    }
    case "REMOVE_TOAST":
      if (action.toastId === undefined) {
        return {
          ...state,
          toasts: [],
        };
      }
      return {
        ...state,
        toasts: state.toasts.filter((t) => t.id !== action.toastId),
      };
    case "UPSERT_TOAST": {
      const existingIndex = state.toasts.findIndex(
        (t) => t.id === action.toast.id,
      );
      if (existingIndex > -1) {
        return {
          ...state,
          toasts: state.toasts.map((t) =>
            t.id === action.toast.id ? { ...t, ...action.toast } : t,
          ),
        };
      }
      return {
        ...state,
        toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
      };
    }
  }
};

const listeners = new Set<(state: State) => void>();

let memoryState: State = { toasts: [] };

function dispatch(action: Action) {
  memoryState = reducer(memoryState, action);
  listeners.forEach((listener) => {
    listener(memoryState);
  });
}

type Toast = Omit<ToasterToast, "id">;

function toast({
  id,
  once,
  ...props
}: Toast & { id?: string; once?: boolean }) {
  const toastId = id || genId();

  // `once` dedupe requires a caller-provided stable `id`. A generated id is
  // unique per call, so it could never match (and would grow the set without
  // bound); gate on `id` so `once` without one is simply a no-op.
  const dedupeOnce = once === true && id !== undefined;

  const update = (props: Toast) =>
    dispatch({
      type: "UPDATE_TOAST",
      toast: { ...props, id: toastId },
    });
  const dismiss = () => dispatch({ type: "DISMISS_TOAST", toastId });
  const upsert = (props: Toast) =>
    dispatch({
      type: "UPSERT_TOAST",
      toast: {
        ...props,
        id: toastId,
        open: true,
        onOpenChange: (open) => {
          if (!open) {
            dismiss();
          }
        },
      },
    });

  const suppressed = dedupeOnce && shownOnceKeys.has(toastId);
  if (dedupeOnce) {
    shownOnceKeys.add(toastId);
  }

  if (!suppressed) {
    dispatch({
      type: "ADD_TOAST",
      toast: {
        ...props,
        id: toastId,
        open: true,
        onOpenChange: (open) => {
          if (!open) {
            dismiss();
          }
        },
      },
    });
  }

  return {
    id: toastId,
    dismiss,
    update,
    upsert,
  };
}

function useToast() {
  const [state, setState] = React.useState<State>(memoryState);

  React.useEffect(() => {
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
  }, [state]);

  return {
    ...state,
    dismiss: (toastId?: string) => dispatch({ type: "DISMISS_TOAST", toastId }),
  };
}

export { useToast, toast };

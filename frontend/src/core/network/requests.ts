/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { invariant } from "@/utils/invariant";
import { store } from "../state/jotai";
import type { EditRequests, RunRequests } from "./types";

export const requestClientAtom = atom<null | (EditRequests & RunRequests)>(
  null,
);

/** React hook for the request client interface */
export function useRequestClient() {
  const client = useAtomValue(requestClientAtom);
  invariant(client, "useRequestClient() requires setting requestClientAtom.");
  return client;
}

/** Imperative getter for the request client interface */
export function getRequestClient() {
  const client = store.get(requestClientAtom);
  invariant(client, "getRequestClient() requires requestClientAtom to be set.");
  return client;
}

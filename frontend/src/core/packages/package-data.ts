/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import type {
  EditRequests,
  PackageOperationResponse,
  RunRequests,
} from "@/core/network/types";
import { store } from "@/core/state/jotai";

export const packageDataVersionAtom = atom(0);
export function invalidatePackageData() {
  store.set(packageDataVersionAtom, (version) => version + 1);
}

/** Refresh package consumers regardless of which UI initiated a mutation. */
export function withPackageInvalidation(
  client: EditRequests & RunRequests,
): EditRequests & RunRequests {
  function invalidateAfter<Request, Response extends PackageOperationResponse>(
    request: (body: Request) => Promise<Response>,
  ) {
    return async (body: Request) => {
      const result = await request(body);
      if (result.success || result.restartRequired) {
        invalidatePackageData();
      }
      return result;
    };
  }
  return {
    ...client,
    addPackage: invalidateAfter(client.addPackage),
    removePackage: invalidateAfter(client.removePackage),
  };
}

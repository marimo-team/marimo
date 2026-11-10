/* Copyright 2026 Marimo. All rights reserved. */

/** The OpenAPI document of the host protocol. */

import type { HttpApi, HttpApiGroup } from "effect/http-api";
import { OpenApi } from "effect/http-api";

const options: OpenApi.FromApiOptions = {
  // Effect names a problem's wire schema `<Class>Encoded`.
  referencePolicy: ({ identifier }) => identifier?.replace(/Encoded$/, ""),
};

/** The document for `Host.Api`, or for an API an extension made with `Host.make`. */
export const fromApi = <
  Id extends string,
  Groups extends HttpApiGroup.Constraint,
>(
  api: HttpApi.HttpApi<Id, Groups>,
) => OpenApi.fromApi(api, options);

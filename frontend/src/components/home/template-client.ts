/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { getRuntimeManager } from "@/core/runtime/config";
import { once } from "@/utils/once";
import { API, createClientWithRuntimeManager } from "../../core/network/api";

export type TemplateCatalogResponse =
  components["schemas"]["TemplateCatalogResponse"];

const getClient = once(() =>
  createClientWithRuntimeManager(getRuntimeManager()),
);

export function listTemplates(): Promise<TemplateCatalogResponse> {
  return getClient().GET("/api/templates/").then(API.handleResponse);
}

export function launchTemplate(templateId: string): Promise<string> {
  return getClient()
    .POST("/api/templates/{template_id}/launch", {
      params: { path: { template_id: templateId } },
    })
    .then(API.handleResponse)
    .then((response) => response.fileKey);
}

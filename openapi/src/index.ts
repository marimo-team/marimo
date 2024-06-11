export * from "./api.d";

import createClient, { ClientOptions } from "openapi-fetch";
import type { paths } from "./api.d";

export function createMarimoClient(opts: ClientOptions) {
  return createClient<paths>(opts);
}

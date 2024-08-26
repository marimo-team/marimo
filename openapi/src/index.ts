export type * from "./api";

import createClient, { type ClientOptions } from "openapi-fetch";
import type { paths } from "./api";

export function createMarimoClient(opts: ClientOptions) {
  return createClient<paths>(opts);
}

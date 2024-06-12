export type * from "./api";

import createClient, { ClientOptions } from "openapi-fetch";
import type { paths } from "./api";

export function createMarimoClient(opts: ClientOptions) {
  return createClient<paths>(opts);
}

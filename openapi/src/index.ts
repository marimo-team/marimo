export type * from "./api";
import type { components as session } from "./session";
import type { components as notebook } from "./notebook";

import createClient, { type ClientOptions } from "openapi-fetch";
import type { paths } from "./api";

export type Session = session["schemas"];
export type Notebook = notebook["schemas"];

export function createMarimoClient(opts: ClientOptions) {
  return createClient<paths>(opts);
}

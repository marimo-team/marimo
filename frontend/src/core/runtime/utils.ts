/* Copyright 2024 Marimo. All rights reserved. */

import { Strings } from "@/utils/strings";

export function urlJoin(first: string, second: string): string {
  first = Strings.withoutTrailingSlash(first);
  second = Strings.withoutLeadingSlash(second);
  return `${first}/${second}`;
}

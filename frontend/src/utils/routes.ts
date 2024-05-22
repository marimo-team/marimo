/* Copyright 2024 Marimo. All rights reserved. */

import { match, Match, MatchFunction } from "path-to-regexp";

export class TinyRouter {
  private routes: Array<{
    template: string;
    pathFunction: MatchFunction;
  }>;

  constructor(templates: string[]) {
    this.routes = templates.map((template) => {
      return {
        template,
        pathFunction: match(template),
      };
    });
  }

  match(location: Location): [Match, template: string] | false {
    for (const { pathFunction, template } of this.routes) {
      const match =
        pathFunction(location.hash) || pathFunction(location.pathname);
      if (match) {
        return [match, template];
      }
    }

    return false;
  }
}

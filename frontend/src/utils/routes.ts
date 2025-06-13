/* Copyright 2024 Marimo. All rights reserved. */

import {
  type Match,
  type MatchFunction,
  match,
  type ParamData,
} from "path-to-regexp";

export class TinyRouter {
  private routes: Array<{
    template: string;
    pathFunction: MatchFunction<ParamData>;
  }>;

  constructor(templates: string[]) {
    this.routes = templates.map((template) => {
      return {
        template,
        pathFunction: match(template),
      };
    });
  }

  match(location: Location): [Match<ParamData>, template: string] | false {
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

/* Copyright 2024 Marimo. All rights reserved. */
import React, {
  type JSX,
  type PropsWithChildren,
  useEffect,
  useMemo,
  useState,
} from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
import { TinyRouter } from "@/utils/routes";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  /**
   * Route paths to render.
   */
  routes: string[];
}

export class RoutesPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-routes";

  validator = z.object({
    routes: z.array(z.string()),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return <RoutesComponent {...props.data}>{props.children}</RoutesComponent>;
  }
}

const RoutesComponent = ({
  routes,
  children,
}: PropsWithChildren<Data>): JSX.Element => {
  const childCount = React.Children.count(children);
  if (childCount !== routes.length) {
    throw new Error(
      `Expected ${routes.length} children, but got ${childCount}`,
    );
  }

  const router = useMemo(() => new TinyRouter(routes), [routes]);
  const [matched, setMatched] = useState<string | null>(() => {
    const match = router.match(globalThis.location);
    return match ? match[1] : null;
  });

  const handleFindMatch = useEvent((location: Location) => {
    const match = router.match(location);
    setMatched(match ? match[1] : null);
  });

  useEffect(() => {
    // Listen for route changes
    const listener = (e: PopStateEvent | HashChangeEvent) => {
      handleFindMatch(globalThis.location);
    };
    globalThis.addEventListener("hashchange", listener);
    globalThis.addEventListener("popstate", listener);
    return () => {
      globalThis.removeEventListener("hashchange", listener);
      globalThis.removeEventListener("popstate", listener);
    };
  }, [handleFindMatch]);

  if (!matched) {
    // eslint-disable-next-line react/jsx-no-useless-fragment
    return <></>;
  }

  const matchedIndex = routes.indexOf(matched);
  const child = React.Children.toArray(children)[matchedIndex];

  // eslint-disable-next-line react/jsx-no-useless-fragment
  return <>{child}</>;
};

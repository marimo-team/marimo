/* Copyright 2023 Marimo. All rights reserved. */
import { useLayoutEffect, useRef } from "react";

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { once } from "@/utils/once";

/**
 * TexPlugin
 *
 * A plugin that renders LaTeX, specialized for how our kernel processes
 * LaTeX.
 */
export class TexPlugin implements IStatelessPlugin<{}> {
  tagName = "marimo-tex";

  validator = z.object({});

  render(props: IStatelessPluginProps<{}>): JSX.Element {
    return (
      <TexComponent tex={props.host.textContent || props.host.innerHTML} />
    );
  }
}

const importKatex = once(async () => {
  return (await import("katex")).default;
});

async function renderLatex(mount: HTMLElement, tex: string): Promise<void> {
  const katex = await importKatex();
  if (tex.startsWith("||(||(") && tex.endsWith("||)||)")) {
    // when $$...$$ is used without newlines before/after the $$.
    katex.render(tex.slice(6, -6), mount, {
      displayMode: true,
      throwOnError: false,
    });
  } else if (tex.startsWith("||(") && tex.endsWith("||)")) {
    katex.render(tex.slice(3, -3), mount, {
      displayMode: false,
      throwOnError: false,
    });
  } else if (tex.startsWith("||[") && tex.endsWith("||]")) {
    katex.render(tex.slice(3, -3), mount, {
      displayMode: true,
      throwOnError: false,
    });
  }
}

const TexComponent = ({ tex }: { tex: string }): JSX.Element => {
  const ref = useRef<HTMLSpanElement>(null);

  // The arithmatex markdown extension we use in Python produces nested
  // marimo-tex tags when $$...$$ math is used in a paragraph, with dummy
  // children that mess with rendering.
  //
  // eg., mo.md("hello $$x$$") produces
  //
  // <marimo-tex class="arithmatex">||(<marimo-tex class="arithmatex">||(x||)</marimo-tex>||)</marimo-tex>
  //
  // while mo.md("$$x$$") produces the expected
  //
  // <marimo-tex class="arithmatex">||[x||]</marimo-tex>
  //
  // The nesting looks like a bug, or at least it makes rendering the latex
  // more annoying. So we just get rid of the nesting here, since there
  // isn't a simple way to do that in Python without bringing in a new
  // dependency.
  //
  // The number of children is always 1 (the LaTeX) or 3 redundant ||(, ||)
  // delimiters as the first and third child, another marimo-tex tag as the
  // second. Only try to render latex in the former case.

  // Re-render when the text content changes.
  useLayoutEffect(() => {
    if (ref.current) {
      renderLatex(ref.current, tex);
    }
  }, [tex]);

  return <span ref={ref} />;
};

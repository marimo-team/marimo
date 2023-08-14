/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren, useLayoutEffect, useRef } from "react";
import katex from "katex";

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";

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
    return <TexComponent>{props.children}</TexComponent>;
  }
}

function renderLatex(element: HTMLElement) {
  const tex = element.textContent || element.innerText;
  if (tex.startsWith("||(||(") && tex.endsWith("||)||)")) {
    // when $$...$$ is used without newlines before/after the $$.
    katex.render(tex.slice(6, -6), element, {
      displayMode: true,
      throwOnError: false,
    });
  } else if (tex.startsWith("||(") && tex.endsWith("||)")) {
    katex.render(tex.slice(3, -3), element, {
      displayMode: false,
      throwOnError: false,
    });
  } else if (tex.startsWith("||[") && tex.endsWith("||]")) {
    katex.render(tex.slice(3, -3), element, {
      displayMode: true,
      throwOnError: false,
    });
  }
}

const TexComponent = ({ children }: PropsWithChildren<{}>): JSX.Element => {
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
    if (ref.current?.firstElementChild) {
      renderLatex(ref.current.firstElementChild as HTMLElement);
    }
  }, [ref.current?.textContent]);

  // When we > 1 children, we're in display math mode, so style accordingly.
  const childrenToRender =
    React.Children.count(children) > 1 ? (
      <div className="block my-4 text-center">
        {React.Children.toArray(children)[1]}
      </div>
    ) : (
      children
    );
  return <span ref={ref}>{childrenToRender}</span>;
};

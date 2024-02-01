/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useLayoutEffect, useRef } from "react";
import { lookupScript, updateScriptCache } from "./scripts";
import { Logger } from "../../../utils/Logger";
import { renderHTML } from "../../../plugins/core/RenderHTML";
import { cn } from "../../../utils/cn";

interface Props {
  html: string;
  inline?: boolean;
  className?: string;
}

export const HtmlOutput: React.FC<Props> = memo(
  ({ html, inline = false, className }) => {
    const nodeRef = useRef<HTMLDivElement>(null);

    useLayoutEffect(() => {
      const outputNode = nodeRef.current;

      if (!outputNode) {
        Logger.error("Output is not initialized");
        return;
      }

      // Cache script sources and run inline script tags
      async function runScripts(outputNode: HTMLDivElement) {
        // eslint-disable-next-line unicorn/prefer-spread
        const scriptNodes = Array.from(outputNode.querySelectorAll("script"));

        for (const scriptNode of scriptNodes) {
          if (scriptNode.src != null && scriptNode.src !== "") {
            let cachedScript = lookupScript(scriptNode.src);

            // Cache script
            if (cachedScript === null) {
              const scriptElement = document.createElement("script");
              scriptElement.src = scriptNode.src;
              scriptElement.type = scriptNode.type;
              cachedScript = { element: scriptElement, loaded: false };
              updateScriptCache(scriptNode.src, cachedScript);
            }

            // Handle load state
            if (!cachedScript?.loaded) {
              const scriptElement = cachedScript.element;
              await new Promise((resolve) => {
                document.head.append(scriptElement);
                scriptElement.addEventListener("load", resolve);
                scriptElement.addEventListener("error", resolve);
              });
              cachedScript.loaded = true;
            }
          } else {
            const code = scriptNode.innerText;
            const fnbody = `"use strict"; return (async () => {${code}})()`;
            try {
              // eslint-disable-next-line no-new-func, @typescript-eslint/no-implied-eval
              await new Function(fnbody)();
            } catch (error) {
              Logger.error("Failed to execute script ", scriptNode);
              Logger.error(error);
            }
          }
        }
      }

      runScripts(outputNode);
    }, [html, nodeRef]);

    if (!html) {
      return null;
    }

    return (
      <div
        className={cn(className, { "inline-flex": inline, block: !inline })}
        ref={nodeRef}
      >
        {renderHTML({ html })}
      </div>
    );
  },
);
HtmlOutput.displayName = "HtmlOutput";

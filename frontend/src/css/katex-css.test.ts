/* Copyright 2026 Marimo. All rights reserved. */

import { readFile } from "node:fs/promises";
import postcss from "postcss";
import { beforeAll, describe, expect, it } from "vitest";
import {
  checkKatexCss,
  generateKatexCss,
  readUpstreamCss,
  stylesheetPath,
} from "../../scripts/katex-css";

let upstream: string;
let generated: string;

beforeAll(async () => {
  upstream = await readUpstreamCss();
  generated = await generateKatexCss(upstream);
});

describe("copied KaTeX stylesheet", () => {
  it("matches the installed package with only documented marimo overrides", async () => {
    await expect(
      checkKatexCss(upstream, await readFile(stylesheetPath, "utf8")),
    ).resolves.toBeUndefined();
  });

  it.each(["added", "removed", "changed"])(
    "detects %s upstream rule without a version change",
    async (change) => {
      const root = postcss.parse(upstream);
      if (change === "added") {
        root.append(
          postcss.parse(
            ".katex .upstream-drift-probe { display: inline-block; }",
          ),
        );
      } else {
        root.walkRules(".katex .mspace", (rule) => {
          if (change === "removed") {
            rule.remove();
          } else {
            rule.append(postcss.decl({ prop: "color", value: "red" }));
          }
        });
      }
      await expect(checkKatexCss(root.toString(), generated)).rejects.toThrow(
        "pnpm sync-katex-css",
      );
      const regenerated = await generateKatexCss(root.toString());
      await checkKatexCss(root.toString(), regenerated);
    },
  );

  it.each(["added", "removed", "changed"])(
    "detects %s local rule",
    async (change) => {
      const root = postcss.parse(generated);
      if (change === "added") {
        root.append(postcss.parse(".katex .unexpected { display: none; }"));
      } else {
        root.walkRules(".katex .mspace", (rule) => {
          if (change === "removed") {
            rule.remove();
          } else {
            rule.append(postcss.decl({ prop: "color", value: "red" }));
          }
        });
      }
      await expect(checkKatexCss(upstream, root.toString())).rejects.toThrow(
        "pnpm sync-katex-css",
      );
    },
  );

  it("preserves math sizing, tag alignment, and equation counters without bundling font faces", () => {
    const root = postcss.parse(generated);
    const declarations = (selector: string) => {
      const values: Record<string, string> = {};
      root.walkRules(selector, (rule) => {
        rule.walkDecls((decl) => {
          values[decl.prop] = decl.value;
        });
      });
      return values;
    };
    expect(declarations(".katex")).toEqual({
      "font-family": '"KaTeX_Main", "Times New Roman", serif',
      "font-size": "110%",
      "font-style": "normal",
      "line-height": "inherit",
      position: "relative",
      "text-indent": "0",
      "text-rendering": "auto",
    });
    expect(
      declarations(".katex-display > .katex > .katex-html > .katex-tag"),
    ).toEqual({ position: "absolute", right: "0", "text-align": "right" });
    expect(declarations("body,\n.katex-display")).toEqual({
      "counter-reset": "katexEqnNo mmlEqnNo",
    });
    expect(declarations(".katex .angl")["border-right"]).toBe("0.049em solid");
    const fontFaces: postcss.AtRule[] = [];
    root.walkAtRules("font-face", (rule) => {
      fontFaces.push(rule);
    });
    expect(fontFaces).toEqual([]);
  });

  it.each(["root", "media"])(
    "preserves SVG rule order and %s scope when upstream adds a competing rule",
    async (scope) => {
      const root = postcss.parse(upstream);
      const svgRules: postcss.Rule[] = [];
      root.walkRules(".katex svg", (rule) => {
        svgRules.push(rule);
      });
      const secondSvg = svgRules[1];
      secondSvg.before(postcss.parse(".katex :is(svg) { stroke-width: 3; }"));
      if (scope === "media") {
        const media = postcss.atRule({ name: "media", params: "print" });
        secondSvg.before(media);
        media.append(secondSvg);
      }

      const svgCascade = (css: string) => {
        const rules: {
          selector: string;
          scope: string;
          strokeWidth: string | undefined;
        }[] = [];
        postcss.parse(css).walkRules((rule) => {
          if (
            rule.selector !== ".katex svg" &&
            rule.selector !== ".katex :is(svg)"
          ) {
            return;
          }
          let strokeWidth: string | undefined;
          rule.walkDecls("stroke-width", (decl) => {
            strokeWidth = decl.value;
          });
          const parent = rule.parent;
          rules.push({
            selector: rule.selector,
            scope:
              parent?.type === "atrule"
                ? `${parent.name} ${parent.params}`
                : "root",
            strokeWidth,
          });
        });
        return rules;
      };
      const regenerated = await generateKatexCss(root.toString());
      expect(svgCascade(regenerated)).toEqual(svgCascade(root.toString()));
      await checkKatexCss(root.toString(), regenerated);
    },
  );

  it("requires review when an overridden upstream declaration changes", async () => {
    await expect(
      generateKatexCss(upstream.replace("line-height:1.2", "line-height:1.3")),
    ).rejects.toThrow("review overrides");
  });
});

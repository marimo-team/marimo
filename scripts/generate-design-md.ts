// Copyright 2026 Marimo. All rights reserved.
// deno-lint-ignore-file no-import-prefix

// Resolve repository-relative source paths portably across operating systems.
import { dirname, fromFileUrl, join, normalize } from "jsr:@std/path@1.1.2";

// Parse TS/CJS config files for token values that are not available as CSS.
import { parse as parseJavaScript } from "npm:@babel/parser@7.28.5";
import type {
  CallExpression,
  Expression,
  File,
  Node,
  ObjectExpression,
} from "npm:@babel/types@7.29.0";

// Normalize CSS colors, declarations, variables, functions, and calc() values.
import { converter, formatHex, parse as parseColor } from "npm:culori@4.0.2";
import postcss from "npm:postcss@8.5.10";
import postcssCalc from "npm:postcss-calc@10.1.1";
import valueParser from "npm:postcss-value-parser@4.2.0";

// Reuse Tailwind's default scales and serialize the final DESIGN.md.
import defaultTheme from "npm:tailwindcss@4.2.2/defaultTheme";
import { stringify as stringifyYaml } from "npm:yaml@2.8.3";

type TokenValue = string | TokenObject;
type TokenObject = { [key: string]: TokenValue };
type CssRoot = ReturnType<typeof postcss.parse>;
type ValueNode = ReturnType<typeof valueParser>["nodes"][number];
type FontSizeToken = string | [
  string,
  { lineHeight?: string; letterSpacing?: string; fontWeight?: string },
];
type TypographyParts = {
  fontFamily?: string;
  fontSize?: string;
  fontWeight?: string;
  lineHeight?: string;
  letterSpacing?: string;
};

const scriptDir = dirname(fromFileUrl(import.meta.url));
const root = normalize(Deno.args[0] ?? join(scriptDir, ".."));
const logoSvgUrl =
  "https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg";

// Only primitive token sources are read; component guidance is kept hand-authored.
const sources = {
  appCss: "frontend/src/css/app/App.css",
  cellCss: "frontend/src/css/app/Cell.css",
  configSchema: "frontend/src/core/config/config-schema.ts",
  dataGridTheme: "frontend/src/plugins/impl/data-editor/themes.ts",
  globalCss: "frontend/src/css/globals.css",
  gridLayout: "frontend/src/components/editor/renderers/grid-layout/plugin.tsx",
  tailwindConfig: "frontend/tailwind.config.cjs",
} as const;

type SourceKey = keyof typeof sources;

// Keep the Tailwind default theme type narrow to the token families we emit.
const tailwindTheme = defaultTheme as unknown as {
  borderRadius: Record<string, string>;
  fontSize: Record<string, FontSizeToken>;
  fontWeight: Record<string, string>;
  letterSpacing: Record<string, string>;
  lineHeight: Record<string, string>;
  spacing: Record<string, string>;
};

// Tuples are [CSS variable name, light token name, optional dark token name].
const colorSpecs = [
  ["background", "background", "background-dark"],
  ["foreground", "foreground", "foreground-dark"],
  ["muted", "surface-muted", "surface-muted-dark"],
  ["muted-foreground", "muted-foreground", "muted-foreground-dark"],
  ["popover", "popover", "popover-dark"],
  ["popover-foreground", "popover-foreground", "popover-foreground-dark"],
  ["card", "card", "card-dark"],
  ["card-foreground", "card-foreground", "card-foreground-dark"],
  ["border", "border", "border-dark"],
  ["input", "input", "input-dark"],
  ["primary", "primary", "primary-dark"],
  ["primary-foreground", "on-primary", "on-primary-dark"],
  ["secondary", "secondary", "secondary-dark"],
  ["secondary-foreground", "on-secondary", "on-secondary-dark"],
  ["accent", "accent", "accent-dark"],
  ["accent-foreground", "on-accent", "on-accent-dark"],
  ["ring", "ring"],
  ["destructive", "destructive"],
  ["destructive-foreground", "on-destructive"],
  ["error", "error"],
  ["error-foreground", "on-error"],
  ["success", "success"],
  ["success-foreground", "on-success"],
  ["action", "action"],
  ["action-hover", "action-hover"],
  ["action-foreground", "on-action"],
  ["link", "link", "link-dark"],
  ["link-visited", "link-visited", "link-visited-dark"],
  ["stale", "stale", "stale-dark"],
  ["cm-background", "code-background", "code-background-dark"],
] as const;

const cssCache = new Map<SourceKey, CssRoot>();
const cssVarCache = new Map<SourceKey, Record<string, string>>();
const astCache = new Map<SourceKey, File>();
const toRgb = converter("rgb");

// The optional first arg lets callers run from any cwd while defaulting to repo root.
const repoPath = (relativePath: string) => join(root, relativePath);
const read = (relativePath: string) =>
  Deno.readTextFileSync(repoPath(relativePath));
const readSource = (source: SourceKey) => read(sources[source]);
// DESIGN.md references tokens with {group.name} strings.
const tokenRef = (group: string, name: string) => `{${group}.${name}}`;
const colorRef = (name: string) => tokenRef("colors", name);
const roundedRef = (name: string) => tokenRef("rounded", name);
const typographyRef = (name: string) => tokenRef("typography", name);

// Parsed CSS and ASTs are shared across token builders.
const cached = <K, V>(cache: Map<K, V>, key: K, build: () => V): V => {
  const value = cache.get(key);
  if (value) {
    return value;
  }
  const next = build();
  cache.set(key, next);
  return next;
};

const cleanCss = (value: string) => value.trim().replace(/\s+/g, " ");

const required = <T>(value: T | undefined, label: string): T => {
  if (value === undefined || value === null || value === "") {
    throw new Error(`Could not find ${label}`);
  }
  return value;
};

const cssRoot = (source: SourceKey) =>
  cached(
    cssCache,
    source,
    () => postcss.parse(readSource(source), { from: sources[source] }),
  );

// Collect custom properties without the leading "--".
const cssVars = (source: SourceKey): Record<string, string> =>
  cached(cssVarCache, source, () => {
    const vars: Record<string, string> = {};
    cssRoot(source).walkDecls((decl) => {
      if (decl.prop.startsWith("--")) {
        vars[decl.prop.slice("--".length)] = cleanCss(decl.value);
      }
    });
    return vars;
  });

// Direct CSS reads are reserved for notebook layout facts owned by CSS.
const cssDeclaration = (
  source: SourceKey,
  selector: string,
  property: string,
) => {
  let value: string | undefined;
  cssRoot(source).walkRules((rule) => {
    if (rule.selector === selector) {
      rule.walkDecls(property, (decl) => {
        value ??= cleanCss(decl.value);
      });
    }
  });
  return required(value, `${source}:${selector}:${property}`);
};

// Split CSS function nodes such as var(...) and light-dark(...) by arguments.
const functionArgs = (node: ValueNode) => {
  if (node.type !== "function") {
    throw new Error("Expected CSS function node");
  }
  const args: ValueNode[][] = [[]];
  for (const child of node.nodes) {
    if (child.type === "div" && child.value === ",") {
      args.push([]);
    } else {
      args.at(-1)?.push(child);
    }
  }
  return args.map((nodes) => valueParser.stringify(nodes).trim());
};

const singleFunction = (value: string) => {
  const nodes = valueParser(value).nodes.filter((node) =>
    node.type !== "space"
  );
  return nodes.length === 1 && nodes[0].type === "function"
    ? nodes[0]
    : undefined;
};

const formatColor = (value: string, matte = "#FFFFFF") => {
  const color = required(toRgb(required(parseColor(value), value)), value);
  const alpha = color.alpha ?? 1;
  if (alpha >= 1) {
    return formatHex(color).toUpperCase();
  }

  // DESIGN.md colors are hex-only, so alpha is composited instead of dropped.
  const base = required(toRgb(required(parseColor(matte), matte)), matte);
  return formatHex({
    mode: "rgb",
    r: color.r * alpha + base.r * (1 - alpha),
    g: color.g * alpha + base.g * (1 - alpha),
    b: color.b * alpha + base.b * (1 - alpha),
  }).toUpperCase();
};

// Resolve var(...) and light-dark(...) into concrete DESIGN.md hex colors.
const resolveColorValue = (
  value: string,
  vars: Record<string, string>,
  mode: "light" | "dark",
  seen = new Set<string>(),
  matte = "#FFFFFF",
): string => {
  const normalized = cleanCss(value);
  const fn = singleFunction(normalized);
  if (fn?.value === "light-dark") {
    const [light, dark] = functionArgs(fn);
    return resolveColorValue(
      mode === "light" ? light : dark,
      vars,
      mode,
      seen,
      matte,
    );
  }
  if (fn?.value === "var") {
    const [nameArg, fallback] = functionArgs(fn);
    const name = nameArg.replace(/^--/, "");
    if (seen.has(name)) {
      throw new Error(`Cycle while resolving --${name}`);
    }
    seen.add(name);
    return resolveColorValue(
      required(vars[name] ?? fallback, `--${name}`),
      vars,
      mode,
      seen,
      matte,
    );
  }
  return formatColor(normalized, matte);
};

// Inline var(...) before postcss-calc reduces dimensions.
const inlineCssVars = (value: string, vars = cssVars("globalCss")) => {
  const parsed = valueParser(value);
  parsed.walk((node) => {
    if (node.type === "function" && node.value === "var") {
      const [name] = functionArgs(node);
      Object.assign(node as ValueNode & { type: string; value: string }, {
        type: "word",
        value: required(vars[name.replace(/^--/, "")], name),
      });
    }
  });
  return parsed.toString();
};

// Normalize calc(...) and CSS variables to stable scalar dimensions.
const reduceDimension = (value: string) => {
  const result = postcss([postcssCalc({})]).process(
    `:root{x:${inlineCssVars(value)}}`,
    { from: undefined },
  );
  let reduced: string | undefined;
  result.root.walkDecls("x", (decl) => {
    reduced = decl.value;
  });
  return cleanCss(required(reduced, value));
};

// Parse TS only for config/grid constants, not for UI component extraction.
const ast = (source: SourceKey) =>
  cached(astCache, source, () =>
    parseJavaScript(readSource(source), {
      sourceType: "unambiguous",
      plugins: ["jsx", "typescript"],
    }));

const isNode = (value: unknown): value is Node =>
  typeof value === "object" && value !== null &&
  typeof (value as { type?: unknown }).type === "string";

// Tiny AST walker avoids pulling in a full Babel traversal dependency.
const walkAst = (value: unknown, visit: (node: Node) => void): void => {
  if (Array.isArray(value)) {
    value.forEach((child) => walkAst(child, visit));
    return;
  }
  if (!isNode(value)) {
    return;
  }
  visit(value);
  for (const [key, child] of Object.entries(value)) {
    if (
      !key.endsWith("Comments") &&
      !["loc", "start", "end", "extra"].includes(key)
    ) {
      walkAst(child, visit);
    }
  }
};

const propName = (name: Node) => {
  if (name.type === "Identifier") {
    return name.name;
  }
  if (name.type === "StringLiteral") {
    return name.value;
  }
  if (name.type === "NumericLiteral") {
    return String(name.value);
  }
};

const callArgument = (call: CallExpression): Expression | undefined => {
  const first = call.arguments[0];
  return isNode(first) && first.type !== "SpreadElement"
    ? first as Expression
    : undefined;
};

const callMethodName = (call: CallExpression) =>
  call.callee.type === "MemberExpression" && !call.callee.computed
    ? propName(call.callee.property)
    : undefined;

const objectProperty = (
  object: ObjectExpression,
  name: string,
): Expression | undefined => {
  for (const property of object.properties) {
    if (property.type === "ObjectProperty" && propName(property.key) === name) {
      return property.value as Expression;
    }
  }
};

const objectPath = (
  object: ObjectExpression,
  path: readonly string[],
): Expression | undefined =>
  path.reduce<Expression | undefined>(
    (current, segment) =>
      current?.type === "ObjectExpression"
        ? objectProperty(current, segment)
        : undefined,
    object,
  );

const objectExpression = (
  expression: Expression | undefined,
  label: string,
): ObjectExpression =>
  required(
    expression?.type === "ObjectExpression" ? expression : undefined,
    label,
  );

const variableInitializer = (
  source: SourceKey,
  name: string,
): Expression | undefined => {
  let value: Expression | undefined;
  walkAst(ast(source), (node) => {
    if (
      value ||
      node.type !== "VariableDeclarator" ||
      node.id.type !== "Identifier" ||
      node.id.name !== name ||
      !node.init ||
      node.init.type.startsWith("TS")
    ) {
      return;
    }
    value = node.init as Expression;
  });
  return value;
};

const moduleExportsObject = (source: SourceKey): ObjectExpression => {
  let value: ObjectExpression | undefined;
  walkAst(ast(source), (node) => {
    if (value || node.type !== "AssignmentExpression") {
      return;
    }
    const left = node.left;
    if (
      left.type === "MemberExpression" &&
      !left.computed &&
      left.object.type === "Identifier" &&
      left.object.name === "module" &&
      propName(left.property) === "exports" &&
      node.right.type === "ObjectExpression"
    ) {
      value = node.right;
    }
  });
  return required(value, `${source}:module.exports`);
};

const callObjectArgument = (
  expression: Expression | undefined,
  methodName: string,
): ObjectExpression | undefined => {
  let value: ObjectExpression | undefined;
  walkAst(expression, (node) => {
    if (
      value ||
      node.type !== "CallExpression" ||
      callMethodName(node) !== methodName
    ) {
      return;
    }
    const first = callArgument(node);
    value = first?.type === "ObjectExpression" ? first : undefined;
  });
  return value;
};

const zodShapeObject = (expression: Expression | undefined) =>
  callObjectArgument(expression, "looseObject") ??
    callObjectArgument(expression, "object");

const methodArgument = (
  expression: Expression | undefined,
  methodName: string,
) => {
  let value: Expression | undefined;
  walkAst(expression, (node) => {
    if (
      value ||
      node.type !== "CallExpression" ||
      callMethodName(node) !== methodName
    ) {
      return;
    }
    value = callArgument(node);
  });
  return value;
};

const returnObjectProperty = (
  source: SourceKey,
  functionName: string,
  propertyName: string,
) => {
  let body: Node | undefined;
  walkAst(ast(source), (node) => {
    if (
      body ||
      node.type !== "FunctionDeclaration" ||
      node.id?.name !== functionName
    ) {
      return;
    }
    body = node.body;
  });

  let value: Expression | undefined;
  walkAst(required(body, `${source}:${functionName}`), (node) => {
    if (
      value ||
      node.type !== "ReturnStatement" ||
      node.argument?.type !== "ObjectExpression"
    ) {
      return;
    }
    value = objectProperty(node.argument, propertyName);
  });
  return value;
};

// Evaluate the small expression subset used by Tailwind/grid config constants.
const numericExpression = (expression: Expression): number | undefined => {
  if (expression.type === "NumericLiteral") {
    return expression.value;
  }
  if (
    expression.type === "BinaryExpression" &&
    expression.operator === "/" &&
    expression.left.type !== "PrivateName"
  ) {
    const left = numericExpression(expression.left);
    const right = numericExpression(expression.right);
    return left !== undefined && right !== undefined ? left / right : undefined;
  }
};

// Convert string, number, and simple template literals to token strings.
const expressionText = (expression: Expression): string | undefined => {
  if (expression.type === "StringLiteral") {
    return expression.value;
  }
  if (expression.type === "NumericLiteral") {
    return String(expression.value);
  }
  if (expression.type === "TemplateLiteral") {
    const nested = expression.expressions[0];
    const value = nested && !nested.type.startsWith("TS")
      ? numericExpression(nested as Expression)
      : undefined;
    return value !== undefined && expression.expressions.length === 1
      ? `${Number(value.toFixed(5))}${
        expression.quasis[1]?.value.cooked ?? expression.quasis[1]?.value.raw ??
          ""
      }`
      : undefined;
  }
};

// Read nested values from frontend/tailwind.config.cjs.
const configValue = (path: readonly string[]) => {
  const expression = objectPath(moduleExportsObject("tailwindConfig"), path);
  return required(
    expression ? expressionText(expression) : undefined,
    path.join("."),
  );
};

const gridInitialLayoutObject = () => {
  const plugin = objectExpression(
    variableInitializer("gridLayout", "GridLayoutPlugin"),
    "GridLayoutPlugin",
  );
  const layout = objectProperty(plugin, "getInitialLayout");
  return required(
    layout?.type === "ArrowFunctionExpression" &&
      layout.body.type === "ObjectExpression"
      ? layout.body
      : undefined,
    "GridLayoutPlugin.getInitialLayout",
  );
};

// Pull numeric layout defaults from the renderer's initial-layout contract.
const gridLayoutDefault = (key: string) => {
  const expression = objectProperty(gridInitialLayoutObject(), key);
  return required(
    expression ? numericExpression(expression) : undefined,
    `GridLayoutPlugin.getInitialLayout:${key}`,
  );
};

const themePath = (path: readonly string[]) =>
  path.reduce<unknown>(
    (current, key) =>
      current && typeof current === "object"
        ? (current as Record<string, unknown>)[key]
        : undefined,
    tailwindTheme,
  );

const themeString = (path: readonly string[]) =>
  String(required(themePath(path), path.join(".")));

// Font CSS vars wrap a var(...) fallback chain; the quoted fallback is the name.
const fontName = (familyVar: string) => {
  const value = cssVars("globalCss")[familyVar];
  const node = value
    ? valueParser(value).nodes.find((part) =>
      part.type === "function" && part.value === "var"
    )
    : undefined;
  const fallback = node ? functionArgs(node).slice(1).join() : value;
  return required(
    valueParser(required(fallback, familyVar)).nodes.find((part) =>
      part.type === "string"
    )?.value,
    familyVar,
  );
};

const fontSizeToken = (name: string): TypographyParts => {
  const token = required(tailwindTheme.fontSize[name], `fontSize.${name}`);
  if (typeof token === "string") {
    return { fontSize: token };
  }
  return Object.fromEntries(
    Object.entries({
      fontSize: token[0],
      lineHeight: token[1].lineHeight,
      letterSpacing: token[1].letterSpacing,
      fontWeight: token[1].fontWeight,
    }).filter(([, value]) => value),
  ) as TypographyParts;
};

const configSchemaField = (path: readonly string[]) => {
  let shape = required(
    zodShapeObject(variableInitializer("configSchema", "UserConfigSchema")),
    "UserConfigSchema",
  );
  let expression: Expression | undefined;
  path.forEach((segment, index) => {
    expression = objectProperty(shape, segment);
    if (index < path.length - 1) {
      shape = required(
        zodShapeObject(expression),
        path.slice(0, index + 1).join("."),
      );
    }
  });
  return required(expression, path.join("."));
};

// Config schema defaults are read from the owning zod field.
const configDefault = (field: string) => {
  const prefault = methodArgument(
    configSchemaField(["display", field]),
    "prefault",
  );
  const value = prefault ? numericExpression(prefault) : undefined;
  return String(required(value, `display.${field}.prefault`));
};

// Shared constructor for Tailwind-backed typography tokens.
const typographyToken = (
  {
    family,
    size,
    fontSize,
    weight = "normal",
    lineHeight,
    letterSpacing = "normal",
  }: {
    family: string;
    size: string;
    fontSize?: string;
    weight?: string;
    lineHeight?: string;
    letterSpacing?: string;
  },
): Required<TypographyParts> => {
  const sizeParts = fontSizeToken(size);
  return {
    fontFamily: fontName(family),
    fontSize: fontSize ?? required(sizeParts.fontSize, `fontSize.${size}`),
    fontWeight: sizeParts.fontWeight ??
      required(tailwindTheme.fontWeight[weight], `fontWeight.${weight}`),
    lineHeight: lineHeight
      ? themeString(["lineHeight", lineHeight])
      : required(sizeParts.lineHeight, `lineHeight.${size}`),
    letterSpacing: sizeParts.letterSpacing ??
      themeString(["letterSpacing", letterSpacing]),
  };
};

// Mirror the frontend CSS variable color set, plus semantic aliases.
const buildColors = () => {
  const vars = cssVars("globalCss");
  const colors: Record<string, string> = {};
  const matte = {
    light: resolveColorValue(
      required(vars.background, "background"),
      vars,
      "light",
    ),
    dark: resolveColorValue(
      required(vars.background, "background"),
      vars,
      "dark",
    ),
  };
  for (const [cssName, lightName, darkName] of colorSpecs) {
    colors[lightName] = resolveColorValue(
      required(vars[cssName], cssName),
      vars,
      "light",
      new Set<string>(),
      matte.light,
    );
    if (darkName) {
      colors[darkName] = resolveColorValue(
        required(vars[cssName], cssName),
        vars,
        "dark",
        new Set<string>(),
        matte.dark,
      );
    }
  }

  // Surface aliases are agent-facing names for existing background/card tokens.
  colors.surface = required(colors.background, "surface");
  colors["surface-dark"] = required(
    colors["card-dark"] ?? colors["background-dark"],
    "surface-dark",
  );
  // The data grid accent is a TS literal, not a CSS custom property.
  colors["data-grid-accent"] = formatColor(
    required(
      expressionText(
        required(
          returnObjectProperty(
            "dataGridTheme",
            "getGlideTheme",
            "accentColor",
          ),
          "data-grid-accent",
        ),
      ),
      "data-grid-accent",
    ),
  );

  return colors;
};

// Keep typography to canonical agent-facing scales, not every UI text variant.
const buildTypography = () => ({
  "body-md": typographyToken({
    family: "text-font",
    size: "base",
    lineHeight: "7",
  }),
  "body-sm": typographyToken({ family: "text-font", size: "sm" }),
  "label-md": typographyToken({
    family: "text-font",
    size: "sm",
    weight: "medium",
    lineHeight: "none",
  }),
  "label-xs": typographyToken({
    family: "text-font",
    size: "xs",
    weight: "semibold",
  }),
  "markdown-heading": typographyToken({
    family: "heading-font",
    size: "3xl",
    weight: "semibold",
    letterSpacing: "tight",
  }),
  "code-editor": typographyToken({
    family: "monospace-font",
    size: "sm",
    fontSize: `${configDefault("code_editor_font_size")}px`,
  }),
  "slide-h1": {
    fontFamily: fontName("text-font"),
    fontSize: configValue([
      "theme",
      "extend",
      "typography",
      "slides",
      "css",
      "h1",
      "fontSize",
    ]),
    fontWeight: required(tailwindTheme.fontWeight.semibold, "semibold"),
    lineHeight: configValue([
      "theme",
      "extend",
      "typography",
      "slides",
      "css",
      "h1",
      "lineHeight",
    ]),
    letterSpacing: themeString(["letterSpacing", "normal"]),
  },
});

// Radius tokens mix Tailwind defaults, Tailwind overrides, and cell CSS.
const buildRounded = () => ({
  sm: reduceDimension(configValue(["theme", "extend", "borderRadius", "sm"])),
  DEFAULT: reduceDimension(required(cssVars("globalCss").radius, "radius")),
  md: reduceDimension(configValue(["theme", "extend", "borderRadius", "md"])),
  lg: reduceDimension(configValue(["theme", "extend", "borderRadius", "lg"])),
  cell: reduceDimension(
    cssDeclaration("cellCss", ".marimo-cell", "border-radius"),
  ),
  xl: themeString(["borderRadius", "xl"]),
  full: themeString(["borderRadius", "full"]),
});

// Spacing includes Tailwind scale values plus notebook layout dimensions.
const buildSpacing = () => ({
  unit: themeString(["spacing", "2"]),
  xs: themeString(["spacing", "1"]),
  sm: themeString(["spacing", "2"]),
  md: themeString(["spacing", "4"]),
  lg: themeString(["spacing", "6"]),
  xl: themeString(["spacing", "12"]),
  "content-compact": required(cssVars("appCss")["content-width"], "content"),
  "content-medium": required(
    cssVars("appCss")["content-width-medium"],
    "content-medium",
  ),
  "content-wide": `${gridLayoutDefault("maxWidth")}px`,
  "grid-row-height": `${gridLayoutDefault("rowHeight")}px`,
  // String form avoids design.md treating this unitless count as a raw number.
  "grid-columns": String(gridLayoutDefault("columns")),
});

// Canonical examples only; prose guidance covers the larger component family.
const buildComponents = () => ({
  "app-shell": {
    backgroundColor: colorRef("background"),
    textColor: colorRef("foreground"),
    typography: typographyRef("body-md"),
  },
  cell: {
    backgroundColor: colorRef("surface"),
    textColor: colorRef("foreground"),
    typography: typographyRef("body-md"),
    rounded: roundedRef("cell"),
    width: cssDeclaration("cellCss", ".marimo-cell", "width"),
  },
  "output-area": {
    backgroundColor: colorRef("surface"),
    textColor: colorRef("foreground"),
    typography: typographyRef("body-md"),
    padding: cssDeclaration("cellCss", ".output-area", "padding"),
    width: cssDeclaration("cellCss", ".output-area", "width"),
  },
  "code-editor": {
    backgroundColor: colorRef("code-background"),
    textColor: colorRef("foreground"),
    typography: typographyRef("code-editor"),
    width: cssDeclaration("cellCss", ".cm", "width"),
  },
  "button-primary": {
    backgroundColor: colorRef("primary"),
    textColor: colorRef("on-primary"),
    typography: typographyRef("label-md"),
    rounded: roundedRef("md"),
    height: themeString(["spacing", "9"]),
  },
  "button-action": {
    backgroundColor: colorRef("action"),
    textColor: colorRef("on-action"),
    typography: typographyRef("label-md"),
    rounded: roundedRef("md"),
    height: themeString(["spacing", "9"]),
  },
  input: {
    backgroundColor: colorRef("background"),
    textColor: colorRef("foreground"),
    typography: typographyRef("code-editor"),
    rounded: roundedRef("sm"),
    height: themeString(["spacing", "6"]),
  },
  "data-table": {
    backgroundColor: colorRef("surface"),
    textColor: colorRef("foreground"),
    typography: typographyRef("body-sm"),
    width: "100%",
  },
});

// Structured tokens emitted at the top of DESIGN.md.
const tokens = (): TokenObject => ({
  version: "alpha",
  name: "marimo",
  description:
    "Design system for marimo, a reactive Python notebook for reproducible, git-friendly, deployable work.",
  colors: buildColors(),
  typography: buildTypography(),
  rounded: buildRounded(),
  spacing: buildSpacing(),
  components: buildComponents(),
});

// Visual identity guidance emitted after the token block.
const body = () =>
  [
    "## Brand Assets",
    "",
    `- Logo SVG: ${logoSvgUrl}`,
    "- Preserve the original aspect ratio.",
    "- Do not recolor unless explicitly requested.",
    "",
    "## Visual Character",
    "",
    "- Compact, software-native, and utilitarian.",
    "- White or near-black work surfaces with slate borders and muted secondary text.",
    "- Restrained blue for primary interaction; yellow for action, stale, or needs-run states.",
    "- Avoid decorative gradients, marketing-style heroes, nested cards, and one-off palettes.",
    "",
    "## Color",
    "",
    "- Use background, surface, foreground, border, and muted tokens for structure.",
    "- Use primary for primary actions, selection, progress, and clear focus only.",
    "- Use action and stale colors for manual action or freshness state, not generic warning.",
    "- Use destructive, error, and success colors only for their semantic states.",
    "- Preserve light and dark token pairs whenever a color appears in both modes.",
    "",
    "## Typography",
    "",
    "- Use PT Sans for UI and prose, Lora for authored markdown headings, and Fira Mono for code-like values.",
    "- Keep control text compact and legible.",
    "- Do not add viewport-based type scaling beyond marimo's app defaults.",
    "",
    "## Surfaces",
    "",
    "- Use borders first and subtle shadows second.",
    "- Cells, outputs, editors, markdown, tables, and data grids should be full-width and overflow-safe.",
    "- Keep data UI dense and inspectable: stable columns, predictable overflow, readable headers, and no decorative framing around tables or charts.",
    "- Cards are for repeated items, dialogs, or genuinely framed tools; do not style page sections as cards.",
    "",
    "## Components",
    "",
    "- Buttons should be compact, label-like, focusable, and drawn from primary, secondary, or action semantics.",
    "- Icon buttons should use familiar existing icons and tooltips for unclear actions.",
    "- Inputs, selects, and textareas should be compact, bordered, readable, and use code typography only for code-like values.",
    "- Tabs, menus, popovers, dialogs, and tooltips should use semantic surfaces, borders, focus states, and restrained shadow.",
    "- Runtime states should pair color with labels, icons, borders, position, or shape.",
    "",
    "## Motion",
    "",
    "Use short transitions for hover, focus, loading, resize, drag, and stale-output changes. Avoid decorative animation.",
  ].join("\n");

const renderDesignMd = () =>
  [
    "---",
    stringifyYaml(tokens(), { lineWidth: 0 }).trimEnd(),
    "---",
    "",
    body(),
    "",
  ].join("\n");

// Print the artifact so Make/CI can either write it or diff it without mutation.
Deno.stdout.writeSync(new TextEncoder().encode(renderDesignMd()));

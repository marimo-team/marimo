/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import type { LanguageAdapter } from "./types";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { parseMixed } from "@lezer/common";
import { python, pythonLanguage } from "@codemirror/lang-python";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";
import {
  type Completion,
  type CompletionContext,
  type CompletionResult,
  type CompletionSource,
  autocompletion,
} from "@codemirror/autocomplete";
import { once } from "lodash-es";
import { enhancedMarkdownExtension } from "../markdown/extension";
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { indentOneTab } from "./utils/indentOneTab";
import { type QuotePrefixKind, splitQuotePrefix } from "./utils/quotes";
import { markdownAutoRunExtension } from "../cells/extensions";
import type { PlaceholderType } from "../config/extension";
import type { CellId } from "@/core/cells/ids";

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ['"', '"'],
  ["'", "'"],
];

// explode into all combinations
//
// A note on f-strings:
//
// f-strings are not yet supported due to bad interactions with
// string escaping, LaTeX, and loss of Python syntax highlighting
const pairs = ["", "r"].flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end]),
);

const regexes = pairs.map(
  ([start, end]) =>
    // mo.md( + any number of spaces + start + capture + any number of spaces + end)
    [
      start,
      new RegExp(`^mo\\.md\\(\\s*${start}(.*)${end}\\s*\\)$`, "s"),
    ] as const,
);

/**
 * Language adapter for Markdown.
 */
export class MarkdownLanguageAdapter implements LanguageAdapter {
  readonly type = "markdown";
  readonly defaultCode = 'mo.md(r"""\n""")';

  static fromMarkdown(markdown: string) {
    return `mo.md(r"""\n${markdown}\n""")`;
  }

  lastQuotePrefix: QuotePrefixKind = "";

  transformIn(pythonCode: string): [string, number] {
    pythonCode = pythonCode.trim();

    // empty string
    if (pythonCode === "") {
      this.lastQuotePrefix = "r";
      return ["", 0];
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];

        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        // store the quote prefix for later when we transform out
        this.lastQuotePrefix = quotePrefix;
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        // string-dedent expects the first and last line to be empty / contain only whitespace, so we pad with \n
        return [dedent(`\n${unescapedCode}\n`).trim(), offset];
      }
    }

    // no match
    this.lastQuotePrefix = "r";
    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    // Get the quote type from the last transformIn
    const prefix = this.lastQuotePrefix;

    // Empty string
    if (code === "") {
      // Need at least a space, otherwise the output will be 6 quotes
      code = " ";
    }

    // We always transform back with triple quotes, as to avoid needing to
    // escape single quotes.
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    // If its one line and not bounded by quotes, write it as single line
    const isOneLine = !code.includes("\n");
    const boundedByQuote = code.startsWith('"') || code.endsWith('"');
    if (isOneLine && !boundedByQuote) {
      const start = `mo.md(${prefix}"""`;
      const end = `""")`;
      return [start + escapedCode + end, start.length];
    }

    // Multiline code
    const start = `mo.md(\n    ${prefix}"""\n`;
    const end = `\n    """\n)`;
    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "") {
      return true;
    }

    if (pythonCode.trim() === "mo.md()") {
      return true;
    }

    // Handle mo.md("foo"), mo.plain_text("bar") in the same line
    // If it starts with mo.md, but we have more than one function call, return false
    if (pythonCode.trim().startsWith("mo.md(")) {
      const tree = pythonLanguage.parser.parse(pythonCode);
      let functionCallCount = 0;

      // Parse the code using Lezer to check for multiple function calls
      tree.iterate({
        enter: (node) => {
          if (node.name === "CallExpression") {
            functionCallCount++;
            if (functionCallCount > 1) {
              return false; // Stop iterating if we've found more than one function call
            }
          }
        },
      });

      // If the function call count is greater than 1, we don't want to show "view as markdown"
      if (functionCallCount > 1) {
        return false;
      }
    }

    return regexes.some(([, regex]) => regex.test(pythonCode));
  }

  getExtension(
    _cellId: CellId,
    _completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    _: PlaceholderType,
  ): Extension[] {
    return [
      markdown({
        codeLanguages: languages,
        extensions: [
          // Wrapper extension to handle f-string substitutions
          {
            wrap: parseMixed((node, input) => {
              const text = input.read(node.from, node.to);
              const overlays: Array<{ from: number; to: number }> = [];

              // Find all { } groupings
              const pattern = /{(.*?)}/g;
              let match: RegExpExecArray | null;

              while ((match = pattern.exec(text)) !== null) {
                const start = match.index + 1;
                const end = pattern.lastIndex - 1;
                overlays.push({ from: start, to: end });
              }

              if (overlays.length === 0) {
                return null;
              }

              return {
                parser: pythonLanguage.parser,
                overlays,
              };
            }),
          },
        ],
      }),
      enhancedMarkdownExtension(hotkeys),
      autocompletion({
        activateOnTyping: true,
        override: [
          emojiCompletionSource,
          lucideIconCompletionSource,
          latexSymbolCompletionSource,
        ],
      }),
      // Markdown autorun
      markdownAutoRunExtension(),
      python().support,
    ];
  }
}

const emojiCompletionSource: CompletionSource = async (context) => {
  // Check if the cursor is at a position where an emoji can be inserted
  if (!context.explicit && !context.matchBefore(/:\w*$/)) {
    return null;
  }

  const emojiList = await getEmojiList();
  const filter = context.matchBefore(/:\w*$/)?.text.slice(1) ?? "";

  return {
    from: context.pos - filter.length - 1,
    options: emojiList,
    validFor: /^[\w:]*$/,
  };
};

// This loads emojis from a CDN
// This only happens for searching for emojis, so when you are not connected to the internet,
// everything works fine, except for autocompletion of emojis
const getEmojiList = once(async (): Promise<Completion[]> => {
  const emojiList = await fetch(
    "https://unpkg.com/emojilib@3.0.11/dist/emoji-en-US.json",
  )
    .then((res) => {
      if (!res.ok) {
        throw new Error("Failed to fetch emoji list");
      }
      return res.json() as unknown as Record<string, string[]>;
    })
    .catch(() => {
      // If we can't fetch the emoji list, just return an empty list
      return {};
    });

  return Object.entries(emojiList).map(([emoji, names]) => ({
    shortcode: names[0],
    label: names.map((d) => `:${d}`).join(" "),
    emoji,
    displayLabel: `${emoji} ${names[0].replaceAll("_", " ")}`,
    apply: emoji,
    type: "emoji",
  }));
});

const lucideIconCompletionSource: CompletionSource = async (context) => {
  // Check if the cursor is at a position where a Lucide icon can be inserted
  if (!context.explicit && !context.matchBefore(/::[\w-]*$/)) {
    return null;
  }

  const iconList = await getLucideIconList();
  const filter = context.matchBefore(/::[\w-]*$/)?.text.slice(2) ?? "";

  return {
    from: context.pos - filter.length - 2,
    options: iconList,
    validFor: /^[\w-:]*$/,
  };
};

// This loads Lucide icons from a CDN
const getLucideIconList = once(async (): Promise<Completion[]> => {
  const iconList = await fetch(
    "https://unpkg.com/lucide-static@0.452.0/tags.json",
  )
    .then((res) => {
      if (!res.ok) {
        throw new Error("Failed to fetch Lucide icon list");
      }
      return res.json() as unknown as Record<string, string[]>;
    })
    .catch(() => {
      // If we can't fetch the icon list, just return an empty list
      return {};
    });

  const asSvg = (iconName: string) => {
    return `https://cdn.jsdelivr.net/npm/lucide-static@0.452.0/icons/${iconName}.svg`;
  };

  return Object.entries(iconList).map(
    ([iconName, aliases]): Completion => ({
      label: `::${iconName}`,
      displayLabel: iconName,
      type: "lucide-icon",
      boost: 10,
      apply: `::lucide:${iconName}::`,
      detail: aliases.join(", "),
      info: () => {
        const img = document.createElement("img");
        img.src = asSvg(iconName);
        img.style.width = "24px";
        img.style.height = "24px";
        return img;
      },
    }),
  );
});

// Completion provider for LaTeX-style UTF-8 symbols
export const latexSymbolCompletionSource = (
  context: CompletionContext,
): CompletionResult | null => {
  const filter = context.matchBefore(/\\\w*$/)?.text.slice(1) ?? "";
  if (!filter && !context.explicit) {
    return null;
  }

  return {
    from: context.pos - filter.length - 1,
    options: getLatexSymbolList(),
    validFor: /^[\w\\]*$/,
  };
};

// Common LaTeX symbols with their UTF-8 equivalents
const getLatexSymbolList = once((): Completion[] => {
  const symbols: Array<[string, string, string?]> = [
    // Greek letters
    ["alpha", "α", "Greek small letter alpha"],
    ["beta", "β", "Greek small letter beta"],
    ["gamma", "γ", "Greek small letter gamma"],
    ["delta", "δ", "Greek small letter delta"],
    ["epsilon", "ε", "Greek small letter epsilon"],
    ["zeta", "ζ", "Greek small letter zeta"],
    ["eta", "η", "Greek small letter eta"],
    ["theta", "θ", "Greek small letter theta"],
    ["iota", "ι", "Greek small letter iota"],
    ["kappa", "κ", "Greek small letter kappa"],
    ["lambda", "λ", "Greek small letter lambda"],
    ["mu", "μ", "Greek small letter mu"],
    ["nu", "ν", "Greek small letter nu"],
    ["xi", "ξ", "Greek small letter xi"],
    ["omicron", "ο", "Greek small letter omicron"],
    ["pi", "π", "Greek small letter pi"],
    ["rho", "ρ", "Greek small letter rho"],
    ["sigma", "σ", "Greek small letter sigma"],
    ["tau", "τ", "Greek small letter tau"],
    ["upsilon", "υ", "Greek small letter upsilon"],
    ["phi", "φ", "Greek small letter phi"],
    ["chi", "χ", "Greek small letter chi"],
    ["psi", "ψ", "Greek small letter psi"],
    ["omega", "ω", "Greek small letter omega"],

    // Capital Greek letters
    ["Gamma", "Γ", "Greek capital letter gamma"],
    ["Delta", "Δ", "Greek capital letter delta"],
    ["Theta", "Θ", "Greek capital letter theta"],
    ["Lambda", "Λ", "Greek capital letter lambda"],
    ["Xi", "Ξ", "Greek capital letter xi"],
    ["Pi", "Π", "Greek capital letter pi"],
    ["Sigma", "Σ", "Greek capital letter sigma"],
    ["Phi", "Φ", "Greek capital letter phi"],
    ["Psi", "Ψ", "Greek capital letter psi"],
    ["Omega", "Ω", "Greek capital letter omega"],

    // Math symbols
    ["pm", "±", "Plus-minus sign"],
    ["mp", "∓", "Minus-plus sign"],
    ["times", "×", "Multiplication sign"],
    ["div", "÷", "Division sign"],
    ["cdot", "⋅", "Dot operator"],
    ["ast", "∗", "Asterisk operator"],
    ["star", "⋆", "Star operator"],
    ["circ", "∘", "Ring operator"],
    ["bullet", "•", "Bullet"],
    ["cap", "∩", "Intersection"],
    ["cup", "∪", "Union"],
    ["uplus", "⊎", "Multiset union"],
    ["sqcap", "⊓", "Square cap"],
    ["sqcup", "⊔", "Square cup"],
    ["vee", "∨", "Logical or"],
    ["wedge", "∧", "Logical and"],
    ["setminus", "∖", "Set minus"],
    ["oplus", "⊕", "Circled plus"],
    ["ominus", "⊖", "Circled minus"],
    ["otimes", "⊗", "Circled times"],
    ["oslash", "⊘", "Circled division slash"],
    ["odot", "⊙", "Circled dot operator"],

    // Relation symbols
    ["leq", "≤", "Less than or equal to"],
    ["geq", "≥", "Greater than or equal to"],
    ["equiv", "≡", "Identical to"],
    ["prec", "≺", "Precedes"],
    ["succ", "≻", "Succeeds"],
    ["sim", "∼", "Tilde operator"],
    ["perp", "⊥", "Up tack"],
    ["mid", "∣", "Divides"],
    ["parallel", "∥", "Parallel to"],
    ["subset", "⊂", "Subset of"],
    ["supset", "⊃", "Superset of"],
    ["subseteq", "⊆", "Subset of or equal to"],
    ["supseteq", "⊇", "Superset of or equal to"],
    ["cong", "≅", "Approximately equal to"],
    ["approx", "≈", "Almost equal to"],
    ["neq", "≠", "Not equal to"],
    ["ne", "≠", "Not equal to"],
    ["propto", "∝", "Proportional to"],

    // Arrows
    ["leftarrow", "←", "Leftward arrow"],
    ["rightarrow", "→", "Rightward arrow"],
    ["Leftarrow", "⇐", "Leftward double arrow"],
    ["Rightarrow", "⇒", "Rightward double arrow"],
    ["leftrightarrow", "↔", "Left right arrow"],
    ["Leftrightarrow", "⇔", "Left right double arrow"],
    ["uparrow", "↑", "Upward arrow"],
    ["downarrow", "↓", "Downward arrow"],
    ["Uparrow", "⇑", "Upward double arrow"],
    ["Downarrow", "⇓", "Downward double arrow"],

    // Miscellaneous
    ["infty", "∞", "Infinity"],
    ["nabla", "∇", "Nabla"],
    ["partial", "∂", "Partial differential"],
    ["forall", "∀", "For all"],
    ["exists", "∃", "There exists"],
    ["nexists", "∄", "There does not exist"],
    ["emptyset", "∅", "Empty set"],
    ["in", "∈", "Element of"],
    ["notin", "∉", "Not an element of"],
    ["sum", "∑", "N-ary summation"],
    ["prod", "∏", "N-ary product"],
    ["int", "∫", "Integral"],
    ["oint", "∮", "Contour integral"],
    ["sqrt", "√", "Square root"],
    ["hbar", "ℏ", "Planck constant over 2pi"],
    ["ldots", "…", "Horizontal ellipsis"],
    ["cdots", "⋯", "Midline horizontal ellipsis"],
    ["vdots", "⋮", "Vertical ellipsis"],
    ["ddots", "⋱", "Down right diagonal ellipsis"],
  ];

  return symbols.map(([command, symbol, description]) => ({
    label: `\\${command}`,
    displayLabel: command,
    type: "latex-symbol",
    boost: 10,
    apply: symbol,
    detail: description || "",
  }));
});

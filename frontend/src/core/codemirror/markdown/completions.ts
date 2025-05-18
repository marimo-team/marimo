/* Copyright 2024 Marimo. All rights reserved. */

import { once } from "@/utils/once";
import type { CompletionSource, Completion } from "@codemirror/autocomplete";

const emojiCompletionSource: CompletionSource = async (context) => {
  // Check if the cursor is at a position where an emoji can be inserted

  // Valid matches:
  // :
  // :emoji
  const match = context.matchBefore(/:\w*$/);

  if (!context.explicit && !match) {
    return null;
  }

  const emojiList = await getEmojiList();

  return {
    from: match?.from ?? context.pos,
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

  // Valid matches:
  // ::
  // ::lucide:
  // ::lucide:icon
  const match = context.matchBefore(/::[\w-:]*$/);

  if (!context.explicit && !match) {
    return null;
  }

  const iconList = await getLucideIconList();

  return {
    from: match?.from ?? context.pos,
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
const latexSymbolCompletionSource: CompletionSource = (context) => {
  // Valid matches:
  // \
  // \alpha
  const match = context.matchBefore(/\\\w*$/);

  if (!context.explicit && !match) {
    return null;
  }

  return {
    from: match?.from ?? context.pos,
    options: getLatexSymbolList(),
    validFor: /^[\w\\]*$/,
  };
};

// Common LaTeX symbols with their UTF-8 equivalents
const getLatexSymbolList = once((): Completion[] => {
  const symbols: Array<[string, string, string]> = [
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
    label: `\\${command} ${description}`, // Include the description so it's searchable
    displayLabel: command,
    type: "latex-symbol",
    boost: 10,
    // We complete the command, instead of the symbol since
    // some commands take arguments.
    apply: `\\${command}`,
    info: () => {
      const div = document.createElement("div");
      div.textContent = `${symbol} ${description}`;
      return div;
    },
    detail: symbol,
  }));
});

export const markdownCompletionSources = [
  emojiCompletionSource,
  lucideIconCompletionSource,
  latexSymbolCompletionSource,
];

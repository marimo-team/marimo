/* Copyright 2026 Marimo. All rights reserved. */

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            fontFamily: "var(--text-font)",
            color: "inherit",
            pre: {
              color: "inherit",
              background: "inherit",
            },
            "code::before": {
              content: "",
            },
            "code::after": {
              content: "",
            },
            code: {
              fontWeight: 500,
            },
            "ul > li::marker": {
              color: "var(--muted-foreground)",
            },
            "ol > li::marker": {
              color: "var(--muted-foreground)",
            },
          },
        },
        slides: {
          // This aims to match Google Slides' typography
          // h1 -> 80px
          // h2 -> 36pts (48px)
          // h3 -> 28pts (37.33px)
          // h4 -> 25pts (33.33px)
          // p -> 18pts (24px)
          // code -> 18pts (24px)
          css: {
            h1: {
              fontSize: `${70 / 16}rem`,
              lineHeight: 1.2,
            },
            "h1 code": {
              fontSize: `${70 / 16}rem`,
            },
            h2: {
              fontSize: `${48 / 16}rem`,
              lineHeight: 1.3,
            },
            "h2 code": {
              fontSize: `${48 / 16}rem`,
            },
            h3: {
              fontSize: `${37 / 16}rem`,
              lineHeight: 1.4,
            },
            "h3 code": {
              fontSize: `${37 / 16}rem`,
            },
            h4: {
              fontSize: `${33 / 16}rem`,
              lineHeight: 1.5,
            },
            "h4 code": {
              fontSize: `${33 / 16}rem`,
            },
            h5: {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
            "h5 code": {
              fontSize: `${24 / 16}rem`,
            },
            h6: {
              fontSize: `${20 / 16}rem`,
              lineHeight: 1.5,
            },
            "h6 code": {
              fontSize: `${20 / 16}rem`,
            },
            p: {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
            li: {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
            ".paragraph": {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
            ".markdown > span.paragraph": {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
            // Set default font size for prose content
            ".prose": {
              fontSize: `${24 / 16}rem`,
              lineHeight: 1.5,
            },
          },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

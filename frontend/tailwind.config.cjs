/* Copyright 2026 Marimo. All rights reserved. */

const plugin = require("tailwindcss/plugin");
const { fontFamily } = require("tailwindcss/defaultTheme");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        prose: ["var(--text-font)", ...fontFamily.sans],
        code: ["var(--monospace-font)", ...fontFamily.mono],
        mono: ["var(--monospace-font)", ...fontFamily.mono],
        heading: ["var(--heading-font)", ...fontFamily.sans],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
        "delayed-show": {
          "0%": { opacity: 0 },
          "99%": { opacity: 0 },
          "100%": { opacity: 1 },
        },
        "ellipsis-dot": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
        slide: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
        "progress-indeterminate": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "delayed-show-200": "delayed-show 200ms ease-out",
        "delayed-show-400": "delayed-show 400ms ease-out",
        "ellipsis-dot": "ellipsis-dot 400ms ease-in-out infinite",
        slide: "slide 1.5s ease-in-out infinite",
        "progress-indeterminate":
          "progress-indeterminate 1.5s ease-in-out infinite",
      },
      gridTemplateColumns: {
        "auto-fit": "repeat(auto-fit, minmax(0, 1fr))",
        "auto-fill": "repeat(auto-fill, minmax(0, 1fr))",
        "auto-fill-200": "repeat(auto-fill, minmax(200px, 1fr))",
        "2-fit": "repeat(2, minmax(0, max-content))",
        "3-fit": "repeat(3, minmax(0, max-content))",
      },
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
  plugins: [
    require("tailwindcss-animate"),
    require("@tailwindcss/typography"),
    plugin(({ addUtilities, addVariant }) => {
      const newUtilities = {
        ".increase-pointer-area-x": {
          border: "none",

          "&::before": {
            content: '""',
            position: "absolute",
            top: "0",
            bottom: "0",
            left: "-50px",
            width: "50px",
          },
          "&::after": {
            content: '""',
            position: "absolute",
            top: "0",
            bottom: "0",
            right: "-50px",
            width: "50px",
          },
        },
      };

      addVariant("fullscreen", "&:fullscreen");
      addUtilities(newUtilities);
    }),
  ],
};

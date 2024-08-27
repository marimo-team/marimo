/* Copyright 2024 Marimo. All rights reserved. */

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
      boxShadow: {
        none: "none",
        // fuzzy shadows
        xxs: "var(--shadow-xxs)",
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        xl: "var(--shadow-xl)",
        // solid shadows
        xsSolid:
          "1px 1px 0px 0px var(--tw-shadow-color, var(--base-shadow-darker)), 0px 0px 2px 0px hsl(0deg 0% 25% / 5%)",
        smSolid:
          "2px 2px 0px 0px var(--tw-shadow-color, var(--base-shadow-darker)), 0px 0px 2px 0px hsl(0deg 0% 25% / 5%)",
        mdSolid:
          "4px 4px 0px 0px var(--tw-shadow-color, var(--base-shadow-darker)), 0 0px 4px 0px hsl(0deg 0% 60% / 5%)",
        lgSolid:
          "5px 6px 0px 0px var(--tw-shadow-color, var(--base-shadow-darker)), 0 0px 4px 0px hsl(0deg 0% 75% / 5%)",
        xlSolid:
          "8px 9px 0px 0px var(--tw-shadow-color, var(--base-shadow-darker)), 0 0px 6px 0px hsl(0deg 0% 85% / 5%)",
        // neutral shadows (used for cells, ...)
        // TODO(akshayka): clean these up to use tw-shadow-color
        smNeutral: "var(--light-shadow)",
        mdNeutral: "var(--medium-shadow)",
        lgNeutral: "var(--heavy-shadow)",
        // accent/error shadows
        smError: "var(--light-shadow-error)",
        smAccent: "var(--light-shadow-accent)",
      },
      maxWidth: {
        contentWidth: "var(--content-width)",
        contentWidthMedium: "var(--content-width-medium)",
      },
      padding: {
        18: "4.5rem",
      },
      colors: {
        border:
          "color-mix(in srgb, var(--border), transparent calc((1 - <alpha-value>) * 100%))",
        input:
          "color-mix(in srgb, var(--input), transparent calc((1 - <alpha-value>) * 100%))",
        ring: "color-mix(in srgb, var(--ring), transparent calc((1 - <alpha-value>) * 100%))",
        background:
          "color-mix(in srgb, var(--background), transparent calc((1 - <alpha-value>) * 100%))",
        foreground:
          "color-mix(in srgb, var(--foreground), transparent calc((1 - <alpha-value>) * 100%))",
        link: "color-mix(in srgb, var(--link))",
        "link-visited": "color-mix(in srgb, var(--link-visited))",
        primary: {
          DEFAULT:
            "color-mix(in srgb, var(--primary), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--primary-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        secondary: {
          DEFAULT:
            "color-mix(in srgb, var(--secondary), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--secondary-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        destructive: {
          DEFAULT:
            "color-mix(in srgb, var(--destructive), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--destructive-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        error: {
          DEFAULT:
            "color-mix(in srgb, var(--error), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--error-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        muted: {
          DEFAULT:
            "color-mix(in srgb, var(--muted), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--muted-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        accent: {
          DEFAULT:
            "color-mix(in srgb, var(--accent), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--accent-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        action: {
          DEFAULT:
            "color-mix(in srgb, var(--action), transparent calc((1 - <alpha-value>) * 100%))",
          hover:
            "color-mix(in srgb, var(--action-hover), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--action-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        popover: {
          DEFAULT:
            "color-mix(in srgb, var(--popover), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--popover-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
        card: {
          DEFAULT:
            "color-mix(in srgb, var(--card), transparent calc((1 - <alpha-value>) * 100%))",
          foreground:
            "color-mix(in srgb, var(--card-foreground), transparent calc((1 - <alpha-value>) * 100%))",
        },
      },
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
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "delayed-show-200": "delayed-show 200ms ease-out",
        "delayed-show-400": "delayed-show 400ms ease-out",
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

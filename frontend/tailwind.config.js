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
        // error shadows
        smError: "var(--light-shadow-error)",
      },
      maxWidth: {
        contentWidth: "var(--content-width)",
        contentWidthMedium: "var(--content-width-medium)",
      },
      padding: {
        18: "4.5rem",
      },
      colors: {
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        link: "hsl(var(--link))",
        "link-visited": "hsl(var(--link-visited))",
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary) / <alpha-value>)",
          foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
        },
        error: {
          DEFAULT: "hsl(var(--error) / <alpha-value>)",
          foreground: "hsl(var(--error-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        action: {
          DEFAULT: "hsl(var(--action) / <alpha-value>)",
          hover: "hsl(var(--action-hover) / <alpha-value>)",
          foreground: "hsl(var(--action-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT: "hsl(var(--popover) / <alpha-value>)",
          foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
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
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    plugin(function ({ addUtilities }) {
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

      addUtilities(newUtilities);
    }),
  ],
};

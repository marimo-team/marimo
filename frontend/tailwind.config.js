/* Copyright 2023 Marimo. All rights reserved. */
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
    },
    extend: {
      maxWidth: {
        contentWidth: "var(--content-width)",
      },
      colors: {
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
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

        calloutNeutralBorder: "var(--callout-neutral-border)",
        calloutNeutralBg: "var(--callout-neutral-bg)",
        calloutAlertBorder: "var(--callout-alert-border)",
        calloutAlertBg: "var(--callout-alert-bg)",
        calloutWarnBorder: "var(--callout-warn-border)",
        calloutWarnBg: "var(--callout-warn-bg)",
        calloutSuccessBorder: "var(--callout-success-border)",
        calloutSuccessBg: "var(--callout-success-bg)",
      },
      fontFamily: {
        prose: "var(--text-font)",
        code: "var(--monospace-font)",
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
  plugins: [require("tailwindcss-animate")],
};

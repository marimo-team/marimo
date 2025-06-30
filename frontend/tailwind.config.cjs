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
        xxs: "0px 0px 2px 0px var(--base-shadow-darker)",
        xs: "1px 1px 2px 0px var(--base-shadow), 0px 0px 2px 0px hsl(0deg 0% 25% / var(--base-shadow-opacity))",
        sm: "2px 2px 2px 0px var(--base-shadow), 0px 0px 2px 0px hsl(0deg 0% 25% / var(--base-shadow-opacity))",
        md: "4px 4px 4px 0px var(--base-shadow), 0 0px 4px 0px hsl(0deg 0% 60% / var(--base-shadow-opacity))",
        lg: "5px 6px 4px 0px var(--base-shadow), 0 0px 4px 0px hsl(0deg 0% 75% / var(--base-shadow-opacity))",
        xl: "8px 9px 4px 0px var(--base-shadow), 0 0px 6px 0px hsl(0deg 0% 85% / var(--base-shadow-opacity))",
        "2xl":
          "10px 12px 10px 0px var(--base-shadow), 0 0px 8px 0px hsl(0deg 0% 90% / var(--base-shadow-opacity))",

        xsSolid:
          "1px 1px 0px 0px var(--base-shadow-darker), 0px 0px 2px 0px hsl(0deg 0% 50% / 20%)",
        smSolid:
          "2px 2px 0px 0px var(--base-shadow-darker), 0px 0px 2px 0px hsl(0deg 0% 50% / 20%)",
        mdSolid:
          "4px 4px 0px 0px var(--base-shadow-darker), 0 0px 2px 0px hsl(0deg 0% 60% / 50%)",
        lgSolid:
          "5px 6px 0px 0px var(--base-shadow-darker), 0 0px 4px 0px hsl(0deg 0% 75% / 50%)",
        xlSolid:
          "7px 8px 0px 0px var(--base-shadow-darker), 0 0px 4px 0px hsl(0deg 0% 85% / 50%)",
        "2xlSolid":
          "10px 12px 0px 0px var(--base-shadow-darker), 0 0px 8px 0px hsl(0deg 0% 90% / 50%)",
      },
      width: {
        contentWidth: "var(--content-width)",
        contentWidthMedium: "var(--content-width-medium)",
      },
      minWidth: {
        contentWidth: "var(--content-width)",
        contentWidthMedium: "var(--content-width-medium)",
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
        shade: "var(--base-shadow)",
        input:
          "color-mix(in srgb, var(--input), transparent calc((1 - <alpha-value>) * 100%))",
        ring: "color-mix(in srgb, var(--ring), transparent calc((1 - <alpha-value>) * 100%))",
        background:
          "color-mix(in srgb, var(--background), transparent calc((1 - <alpha-value>) * 100%))",
        foreground:
          "color-mix(in srgb, var(--foreground), transparent calc((1 - <alpha-value>) * 100%))",
        link: "var(--link)",
        "link-visited": "var(--link-visited)",
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
        stale: "var(--stale)",
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
        "ellipsis-dot": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
        slide: {
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

/* Copyright 2024 Marimo. All rights reserved. */
const config = {
  plugins: [
    require("tailwindcss/nesting"),
    require("tailwindcss"),
    process.env.VITE_MARIMO_ISLANDS === "true"
      ? require("postcss-plugin-namespace")(".marimo", {
          ignore: [".marimo", "html", ".marimo:is(.dark *)"],
        })
      : undefined,
    process.env.NODE_ENV === "production" ? require("cssnano") : undefined,
    require("@csstools/postcss-light-dark-function"),
    require("autoprefixer"),
  ],
};

module.exports = config;

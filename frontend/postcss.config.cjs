/* Copyright 2024 Marimo. All rights reserved. */
const config = {
  plugins: [
    require("tailwindcss/nesting"),
    require("tailwindcss"),
    process.env.VITE_MARIMO_ISLANDS === "true"
      ? require("postcss-plugin-namespace")(".marimo", {
          ignore: [".marimo", "html", "body"],
        })
      : undefined,
    process.env.NODE_ENV === "production" ? require("cssnano") : undefined,
    require("autoprefixer"),
  ],
};

module.exports = config;

/* Copyright 2024 Marimo. All rights reserved. */
module.exports = {
  plugins: {
    "tailwindcss/nesting": {},
    tailwindcss: {},
    ...(process.env.NODE_ENV === "production" ? { cssnano: {} } : {}),
    autoprefixer: {},
  },
};

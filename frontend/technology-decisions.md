# Technology Decisions

Quick-hit list of technologies used and why, for the frontend.

- [Vite](https://vitejs.dev/) - Fast dev server, great devX, and a good fit for our needs. Marimo is Javascript heavy so using any SSR framework is not necessary at the moment (although Vite does support SSR frameworks that can be added as plugins).
- [TailwindCSS](https://tailwindcss.com/) - Utility-first CSS framework. It has a great API for theming to enforce design system consistency. Large community and ecosystem.
- [Radix UI](https://www.radix-ui.com/) - Unstyled Component Library that's accessible and has a good API.
- [Radix Colors](https://www.radix-ui.com/colors) - Color palette. It's a great color palette that's accessible and has a good range of colors, supporting light and dark modes.
- [ESLint](https://eslint.org/) - Linter for Typescript. Pretty much the standard for linting.
- [Biome](https://biomejs.dev/) - Fast code formatter
- [MSW](https://mswjs.io/) - Mocking library for API calls. Great for testing and development.
- [Playwright](https://playwright.dev/) - E2E testing library. Great for testing and development. It's faster than Cypress and has a better API.
- [jotai](https://jotai.org/) - State management library to avoid re-renders. Great for simple state management. It's a lot simpler than Redux and has a better API.
- [@tanstack/react-query](https://tanstack.com/query) - Data fetching library for managing server state. Provides caching, background updates, optimistic updates, and mutation management for complex backend interactions.

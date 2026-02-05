# E2E Tests

E2E tests use Playwright.

## Running Tests

```bash
pnpm playwright test                           # Run all e2e tests
pnpm playwright test e2e-tests/slides.spec.ts  # Run specific test
pnpm playwright test --ui                      # Interactive UI mode
```

## Rebuild Before Taking Screenshots

Rebuild the frontend for tests that take screenshots to view the latest changes.

```bash
make fe
pnpm playwright test
```

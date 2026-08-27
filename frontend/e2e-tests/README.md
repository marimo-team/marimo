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

## Visual Regression Tests

The focused visual suite protects shared theme, typography, chrome, and layout behavior. It uses the deterministic fixture in `py/visual_tokens.py`.

### Run the visual suite

If frontend files changed, rebuild the frontend from the repository root:

```bash
make fe
```

Run the focused suite from `frontend/`:

```bash
pnpm playwright test e2e-tests/visual-regression.spec.ts --project=chromium
```

### Update visual baselines

CAUTION: Generate committed baselines on Ubuntu 24.04. Native macOS images use a different platform suffix.

Run this command from `frontend/`:

```bash
pnpm playwright test e2e-tests/visual-regression.spec.ts --project=chromium --update-snapshots
```

Review every changed PNG. Then run the suite again without `--update-snapshots`.

### Add a visual assertion

Add a visual assertion for a shared semantic token, theme behavior, typography, product chrome, or responsive layout.

If pixels do not express the requirement, use a DOM or behavior assertion. Do not add screenshots to every functional E2E test.

If the existing fixture contains the affected semantic role, reuse it. Add a fixture state only for a named planned change.

### Review a baseline change

Use the Playwright report to compare the expected, actual, and difference images. Make sure that each changed region matches the stated product change.

Never use `--update-snapshots` to silence an unexplained failure. Correct the fault or unstable state before a baseline update.

Make sure that unrelated baselines stay unchanged. State the visual reason for each baseline change in the pull-request summary.

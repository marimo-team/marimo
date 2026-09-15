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

Visual snapshots are captured in the same pinned Playwright container locally
and in CI. On macOS, the script uses the Docker CLI with OrbStack or another
Docker-compatible runtime.

From the repository root, build the frontend and run the focused suite:

```bash
make visual-test
```

### Update visual baselines

Generate committed baselines with the pinned container, not with native
Playwright. From the repository root, run:

```bash
make visual-update
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

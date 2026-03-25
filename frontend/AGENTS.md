# Frontend Guidelines

## Key Principles

- Write clear, maintainable code over clever/short syntax
- Use TypeScript with proper typing for all code
- Use functional programming patterns; avoid classes
- Favor composition over inheritance
- Reduce code duplication, if you see code that is repeated, refactor it to a function or component. This standardizes the codebase.

## Naming Conventions

- **Directories**: lowercase with dashes (`components/auth-wizard/`)
- **Components**: PascalCase (`DashboardMenu.tsx`)
- **Variables**: descriptive with auxiliary verbs (`isLoading`, `hasError`, `canSubmit`)

## Testing

### Unit Tests

Tests live alongside source files or in `__tests__` directories.

```bash
pnpm turbo --filter @marimo-team/frontend test                            # All tests
pnpm turbo --filter @marimo-team/frontend test src/__tests__/lru.test.ts  # Specific file
```

Best practices:
- test edge cases
- use descriptive names
- group with `describe`
- prefer complete assertions over individual property checks (e.g., `expect(result).toEqual(expected)` rather than checking each property separately)

### E2E Tests

E2E tests use Playwright. See [e2e-tests/README.md](e2e-tests/README.md) for details.

## Code Quality

Avoid as much as possible using type assertions as they can cause runtime errors. Instead, use type guards, type predicates and error handling.
```typescript
callFunction(x as T) // Avoid this
```

- Use logNever or assertNever to handle exhaustive switch cases.
```typescript
switch (value) {
  case "a":
    break;
  default:
    logNever(value);
}
```

- Keep comments minimal. Comments should only explain "why", not "what".

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

## Performance in repeated components

- For shared DOM subscriptions, use `createSharedSubscription` from `src/utils/shared-resource.ts`.
  For shared resources without notifications, use `createSharedResource` from the same module.
  Define these subscriptions at module scope. When the consumer unmounts or the plugin is destroyed, release its subscription.
- For debounced CodeMirror analysis, use `createDebouncedEditorUpdate` from `src/core/codemirror/debounced-editor-update.ts`.
  Read the current state in its compute callback. When the result is unchanged, return `undefined`.
  Call `destroy()` from the plugin's cleanup. Compare positions and metadata as well as array lengths.
- When an optional feature is disabled, pass `null` to `useEventListener`.
- Mount per-cell menu roots only while open, or share one root across the notebook.
  Preserve trigger identity, keyboard focus, touch gestures, and nested menus.
- Give layout effects explicit dependencies. When a component has no visible content, avoid layout reads.
- Test listener, dispatch, and layout-read counts in normal unit tests. Avoid timing thresholds for these guarantees.
  Cover repeated mounts, final cleanup, queued work after destruction, unchanged results, and changed results.

- Use `useLazyEditorMount` for cell editor registration, viewport eligibility, and destruction.
  Keep construction inside its `build` callback so deferred editors use the latest code and configuration.
- Use a module-level `createSharedIntersectionObserver` for repeated components with the same viewport options.
  Use `useSharedIntersectionObserver` to manage React subscriptions, including disable and cleanup.
  Keep its callback stable with `useCallback`. The final release disconnects the shared observer.
- Return the disposer from `editorMountScheduler.request` in effect cleanup.
  This disposer cannot cancel a newer registration for the same cell.
  Keep dormant registrations separate from runnable queues; do not scan dormant cells when scheduling work.
- Read notebook document text for operations across all cells.
  Use `getAllEditorViews` only for mounted-view effects, and `ensureCellEditorView` for explicit navigation or editing.
- Keep resource-count tests in the normal Vitest suite.
  Cover 500 consumers, duplicate disposal, late callbacks, StrictMode, Activity hide/show, and updated inputs before deferred construction.
  Use `src/__mocks__/intersection-observer.ts` to deliver viewport events without browser timing.

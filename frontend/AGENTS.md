# Frontend Guidelines

You are an expert in React, TypeScript, TailwindCSS, Jotai, Radix UI, Zod, React Hook Form, and modern UX design.

## Key Principles

- Write clear, maintainable code over clever/short syntax
- Use TypeScript with proper typing for all code
- Use functional programming patterns; avoid classes
- Favor composition over inheritance

## Naming Conventions

- **Directories**: lowercase with dashes (`components/auth-wizard/`)
- **Components**: PascalCase (`DashboardMenu.tsx`)
- **Variables**: descriptive with auxiliary verbs (`isLoading`, `hasError`, `canSubmit`)

## Path Aliases

```typescript
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
```

## Lazy Loading

Use lazy loading for components that require heavy dependencies.

```typescript
import { lazy } from "react";
const LazyComponent = lazy(() => import("@/components/LazyComponent"));
```

## State Management with Jotai

While React hooks are preferred, Jotai is useful when you need to persist state outside of the React component tree or store in local storage.

Use `createReducerAndAtoms` for complex state, `atomFamily` for per-item atoms:

```typescript
import { atom, useAtomValue } from "jotai";
import { atomFamily } from "jotai/utils";
import { createReducerAndAtoms } from "@/utils/createReducer";

// Complex state with reducer pattern
const { useActions, valueAtom: notebookAtom } = createReducerAndAtoms(initialState, {
  createNewCell: (state, action: CreateNewCellAction) => ({ ...state, /* changes */ }),
});

// Derived atoms
export const cellIdsAtom = atom((get) => get(notebookAtom).cellIds);

// Per-item atoms (clean up with .remove() to prevent memory leaks)
export const cellDataAtom = atomFamily((cellId: CellId) =>
  atom((get) => get(notebookAtom).cellData[cellId])
);

// Imperative access outside React
import { store } from "@/core/state/jotai";
export const getNotebook = () => store.get(notebookAtom);

// Local storage
const sessionAtom = atomWithStorage<SessionState>("marimo:session", initialState, jotaiJsonStorage);
```

## UI and Styling

Use Tailwind with the `cn` utility. Custom UI components wrap Radix primitives in `@/components/ui/`:

```typescript
import { cn } from "@/utils/cn";

<div className={cn(
  "inline-flex items-center justify-center rounded-md",
  isActive && "bg-primary text-primary-foreground"
)} />
```

## Forms

Use React Hook Form with Zod validation:

```typescript
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({ name: z.string().min(1), email: z.string().email() });
const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
```

## Testing

Tests live alongside source files or in `__tests__` directories.

```bash
pnpm --filter @marimo-team/frontend test                            # All tests
pnpm --filter @marimo-team/frontend test src/__tests__/lru.test.ts  # Specific file
```

Best practices
- test edge cases
- use descriptive names
- group with `describe`

## Type Patterns

```typescript
// Pick/Omit for derived types
type CellBasics = Pick<CellRuntimeState, "status" | "output">;
interface ButtonProps extends Omit<VariantProps<typeof buttonVariants>, "disabled"> {}

// Record for object types
type Variables = Record<CellId, CellData>;

// Type guards
function isErrorMime(mimetype?: string): boolean {
  return mimetype === "application/vnd.marimo+error";
}
```

## Code Quality

```typescript
import { logNever } from "@/utils/logNever";
import { Logger } from "@/utils/Logger";

// Exhaustive switch handling
logNever(value);

// Logging
Logger.warn(`Cell ${cellId} not found`);
Logger.error(`Error in reducer:`, error);
```

Keep comments minimal. Comments should only explain "why", not "what".

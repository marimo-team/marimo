/* Copyright 2026 Marimo. All rights reserved. */

import {
  BookOpenIcon,
  BugIcon,
  DatabaseIcon,
  FileSearchIcon,
  ListChecksIcon,
  type LucideIcon,
  NetworkIcon,
  NotebookIcon,
  PencilIcon,
  PlusIcon,
  ScanSearchIcon,
  SquareTerminalIcon,
  Trash2Icon,
  VariableIcon,
  WrenchIcon,
} from "lucide-react";
import { formatToolName } from "./shared";

interface ToolDescription {
  label: string;
  /** Short identifying text, e.g. the first line of an added cell. */
  detail?: string;
  icon: LucideIcon;
}

type Phase = "running" | "done";

const KNOWN_TOOLS: Record<
  string,
  { running: string; done: string; icon: LucideIcon }
> = {
  get_marimo_rules: {
    running: "Reading marimo guidelines",
    done: "Read marimo guidelines",
    icon: BookOpenIcon,
  },
  get_active_notebooks: {
    running: "Listing notebooks",
    done: "Listed notebooks",
    icon: NotebookIcon,
  },
  get_lightweight_cell_map: {
    running: "Reading notebook",
    done: "Read notebook",
    icon: FileSearchIcon,
  },
  get_cell_runtime_data: {
    running: "Inspecting cells",
    done: "Inspected cells",
    icon: ScanSearchIcon,
  },
  get_cell_outputs: {
    running: "Reading cell outputs",
    done: "Read cell outputs",
    icon: ScanSearchIcon,
  },
  get_tables_and_variables: {
    running: "Reading variables",
    done: "Read variables",
    icon: VariableIcon,
  },
  get_database_tables: {
    running: "Reading database tables",
    done: "Read database tables",
    icon: DatabaseIcon,
  },
  get_notebook_errors: {
    running: "Checking for errors",
    done: "Checked for errors",
    icon: BugIcon,
  },
  lint_notebook: {
    running: "Linting notebook",
    done: "Linted notebook",
    icon: ListChecksIcon,
  },
  get_cell_dependency_graph: {
    running: "Reading dependency graph",
    done: "Read dependency graph",
    icon: NetworkIcon,
  },
};

const EDIT_LABELS = {
  add_cell: { running: "Adding cell", done: "Added cell", icon: PlusIcon },
  update_cell: {
    running: "Editing cell",
    done: "Edited cell",
    icon: PencilIcon,
  },
  delete_cell: {
    running: "Deleting cell",
    done: "Deleted cell",
    icon: Trash2Icon,
  },
} as const;

/** Describe a tool call in plain language for the activity timeline. */
export function describeToolCall(
  toolName: string,
  input: unknown,
  phase: Phase,
): ToolDescription {
  const name = formatToolName(toolName);

  if (name === "execute_code") {
    return {
      label: phase === "running" ? "Running code" : "Ran code",
      detail: isRecord(input) ? summarizeCode(input.code) : undefined,
      icon: SquareTerminalIcon,
    };
  }

  if (name === "edit_notebook_tool") {
    const edit = getEdit(input);
    if (edit) {
      const labels = EDIT_LABELS[edit.type];
      return {
        label: labels[phase],
        detail: summarizeCode(edit.code),
        icon: labels.icon,
      };
    }
    return {
      label: phase === "running" ? "Editing notebook" : "Edited notebook",
      icon: PencilIcon,
    };
  }

  const known = KNOWN_TOOLS[name];
  if (known) {
    return { label: known[phase], icon: known.icon };
  }

  return {
    label: phase === "running" ? "Calling" : "Called",
    detail: name,
    icon: WrenchIcon,
  };
}

function getEdit(
  input: unknown,
): { type: keyof typeof EDIT_LABELS; code?: string } | undefined {
  if (!isRecord(input) || !isRecord(input.edit)) {
    return undefined;
  }
  const { type, code } = input.edit;
  if (typeof type !== "string" || !(type in EDIT_LABELS)) {
    return undefined;
  }
  return {
    type: type as keyof typeof EDIT_LABELS,
    code: typeof code === "string" ? code : undefined,
  };
}

/** The first line that says what the code does, skipping imports and comments. */
function summarizeCode(code: unknown): string | undefined {
  if (typeof code !== "string") {
    return undefined;
  }
  const lines = code
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  return lines.find((line) => !/^(import\s|from\s|#)/.test(line)) ?? lines[0];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

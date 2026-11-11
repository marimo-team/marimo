/* Copyright 2026 Marimo. All rights reserved. */

/** What an execution produces as it runs and the names it binds. */

import { Schema } from "effect";
import { Integer } from "../internal/schema.ts";
import { ExecutionId, ItemId } from "./Ids.ts";
import { DisplayData, Revision } from "./Execution.ts";

export const Console = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId,
  seq: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description:
      "Position among the execution's items, increasing in the order they were produced.",
  }),
  name: Schema.Literals(["stdout", "stderr"]).annotateKey({
    description: "Which stream the text went to.",
  }),
  text: Schema.String.annotateKey({
    description: "The text, exactly as written.",
  }),
}).annotate({
  description:
    "Text an execution wrote to stdout or stderr. Items are ordinary\nobjects: a producer replaces one by sending it again with the\nsame id, and items are removed with their execution.\n",
  identifier: "Console",
});

export const Display = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId,
  seq: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description:
      "Position among the execution's items, increasing in the order they were produced.",
  }),
  content: DisplayData.annotateKey({ description: "The rendered value." }),
}).annotate({
  description:
    "A value an execution showed as a side effect, such as a figure\nfrom `plt.show()`. A producer replaces one by sending it again\nwith the same id, which is how a progress bar updates in place.\n",
  identifier: "Display",
});

export const InputStatus = Schema.Literals([
  "pending",
  "answered",
  "cancelled",
]).annotate({
  description:
    "An input starts `pending` while it waits for an answer. It becomes\n`answered` when the host accepts a reply for delivery, or `cancelled`\nwhen the host ends the wait while input is still pending. Both\n`answered` and `cancelled` are final. An answered input stays\nanswered if execution later fails before consuming the value.\n",
  identifier: "InputStatus",
});

export const Input = Schema.Struct({
  id: ItemId.annotateKey({
    description:
      "Identifies this prompt uniquely across executions and runtime restarts.",
  }),
  execution_id: ExecutionId,
  seq: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description:
      "Position among the execution's console, display, and input items, increasing in production order.",
  }),
  prompt: Schema.String.annotateKey({
    description: "The prompt to display, which may be empty.",
  }),
  password: Schema.Boolean.annotateKey({
    description: "Whether clients must obscure the value as it is entered.",
  }),
  status: InputStatus,
}).annotate({
  description:
    "A running execution's request for a line of text. Its identity,\nexecution, prompt, password flag, and position stay fixed while\nits status tracks the request. The record remains with its\nexecution after it is answered or cancelled. Submitted answers\ntravel through the reply endpoint to the runtime.\n",
  identifier: "Input",
});

export const Variable = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId.annotateKey({
    description: "The execution that bound the name.",
  }),
  name: Schema.String.annotateKey({
    description: "The name in the namespace.",
  }),
  revision: Revision,
  type: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The runtime's label for the value's type. A host may leave it null.",
  }),
  preview: Schema.NullOr(Schema.String).annotateKey({
    description: "A short rendering of the value. A host may leave it null.",
  }),
}).annotate({
  description:
    "A name a cell's execution bound in the notebook's namespace, with\nthe revision of its value. The execution binds it as it ends, and\nthe item is removed with the execution. An update, as when a\nstate setter runs or a client sets a value, advances the revision\nwithout binding again, and the producer sends the item again with\nthe same id. Hosts publish a cell execution's variables before its\n`completed` status, and remove a cell's previous execution and\nits items before publishing the next one. A scratch execution's\nnames live only while it runs, so it publishes no variables.\n",
  identifier: "Variable",
});

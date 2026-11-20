/* Copyright 2026 Marimo. All rights reserved. */

/** What an execution produces as it runs and the names it binds. */

import { Schema } from "effect";
import { Integer } from "../internal/schema.ts";
import { ExecutionId, ItemId } from "./Ids.ts";
import { Media, Revision } from "./Execution.ts";

export const ConsoleText = Schema.Struct({
  kind: Schema.Literal("text"),
  stream: Schema.Literals(["stdout", "stderr"]).annotateKey({
    description: "Which stream the text went to.",
  }),
  text: Schema.String.annotateKey({
    description: "The text, exactly as written.",
  }),
}).annotate({ identifier: "ConsoleText" });

export const ConsoleMedia = Schema.Struct({
  kind: Schema.Literal("media"),
  media: Media.annotateKey({
    description:
      "Something rendered into the console, such as a figure from `plt.show()` or a formatted traceback.",
  }),
}).annotate({ identifier: "ConsoleMedia" });

export const ConsoleContent = Schema.Union([
  ConsoleText,
  ConsoleMedia,
]).annotate({ identifier: "ConsoleContent" });

export const Console = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId,
  seq: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description:
      "Position among the execution's console and input items, increasing in the order they were produced.",
  }),
  content: ConsoleContent.annotateKey({
    description: "What was written, tagged on `kind`.",
  }),
}).annotate({
  description:
    "One entry in an execution's console, which is text written to\nstdout or stderr, or media rendered among it. A producer replaces\nan entry by sending it again with the same id, and entries are\nremoved with their execution.\n",
  identifier: "Console",
});

export const Output = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId,
  media: Schema.NullOr(Media).annotateKey({
    description:
      "The output as last rendered. Null when the code set it to nothing or cleared it.",
  }),
}).annotate({
  description:
    "What an execution's code shows as its result, such as the value of\na cell's last expression. An execution has at most one, published\nonce the code first sets it. A producer replaces it by sending it\nagain with the same id, including after the execution completes,\nand it is removed with its execution.\n",
  identifier: "Output",
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
      "Position among the execution's console and input items, increasing in production order.",
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
    "A name a cell's execution bound in the notebook's namespace, with\nthe revision of its value. The execution binds it as it ends, and\nthe item is removed with the execution. An update, as when a\nstate setter runs or a UI element's value changes, advances the revision\nwithout binding again, and the producer sends the item again with\nthe same id. Hosts publish a cell execution's variables before its\n`completed` status, and remove a cell's previous execution and\nits items before publishing the next one. A scratch execution's\nnames live only while it runs, so it publishes no variables.\n",
  identifier: "Variable",
});

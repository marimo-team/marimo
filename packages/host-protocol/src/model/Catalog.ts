/* Copyright 2026 Marimo. All rights reserved. */

/** The host and the projects and notebooks it presents. */

import { Schema } from "effect";
import { ProjectId, NotebookId } from "./Ids.ts";

export const Host = Schema.Struct({
  operations: Schema.Array(Schema.String).annotateKey({
    description:
      "The operations this host implements, such as `runtime.start`. Whether a client may call one on a given project or notebook is that object's `operations`. Clients accept names they do not recognize.",
  }),
}).annotate({
  description:
    "What the host can do. There is exactly one host object, and it is\nthe first object in a snapshot when the filter includes `host`.\nA resumed stream only sends it if its operations changed since\nthe cursor. The host sends it again if its operations change.\n",
  identifier: "Host",
});

export const ProjectStatus = Schema.Literals([
  "indexing",
  "indexed",
  "partial",
]).annotate({
  description:
    "How far a host has gotten finding the notebooks in a project.\nWhile it is `indexing`, more notebooks are coming. Once it is\n`indexed`, the host believes it has found every notebook under the\nroot. A `partial` project is one the host stopped scanning on\npurpose, or one with something it could not read.\n",
  identifier: "ProjectStatus",
});

export const Project = Schema.Struct({
  id: ProjectId,
  name: Schema.String.annotateKey({
    description:
      "A label to show people, usually the name of the root directory.",
  }),
  root: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The absolute path of the project's directory, written the way the host's operating system writes paths. Null when the project has no directory.",
  }),
  status: ProjectStatus,
  message: Schema.NullOr(Schema.String).annotateKey({
    description:
      "Why the host stopped scanning. Null unless `status` is `partial`.",
  }),
  operations: Schema.Array(Schema.String).annotateKey({
    description:
      "Operations this client may call on the project, today `notebook.create`. A subset of `host.operations` selected by the client's permissions, independently of the project's current state. The host sends the project again when it changes.",
  }),
}).annotate({
  description:
    "A project is a group of notebooks that the host presents together, usually a directory.",
  identifier: "Project",
});

export const Notebook = Schema.Struct({
  id: NotebookId,
  project_id: ProjectId,
  path: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The file's path relative to the project root, written the way the host's operating system writes paths. Null when the notebook has no file, such as one not yet saved, or one deleted while a runtime still refers to it.",
  }),
  name: Schema.String.annotateKey({
    description:
      "A label to show people. Derived from the filename when the host has nothing better.",
  }),
  operations: Schema.Array(Schema.String).annotateKey({
    description:
      "Operations this client may call on the notebook, such as `notebook.edit` or `runtime.start`. A subset of `host.operations` selected by the client's permissions, independently of the notebook's current state. The `runtime` object shows whether a runtime is attached, and preconditions still apply when an operation is called. The host sends the notebook again when it changes.",
  }),
  updated_at: Schema.NullOr(Schema.String).annotateKey({
    description:
      "When the file was last modified, as of the host's last look at it. Null when the host does not know.",
    format: "date-time",
  }),
}).annotate({
  description:
    "A notebook is a document and its results as the host knows them,\nusually backed by a file. Its kernel, when it has one, is a\nseparate object, the runtime. A host sends at most one `notebook`\nevent per second for the same notebook, since `updated_at`\nchanges on every save.\n",
  identifier: "Notebook",
});

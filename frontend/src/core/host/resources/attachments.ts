/* Copyright 2026 Marimo. All rights reserved. */

import type { Attachment } from "@marimo-team/client/protocol";
import type { Resource } from "@marimo-team/client/reducer";

/** Attachment records retained with the stream's resume cursor. */
export const attachments: Resource<readonly Attachment[], "attachment"> = {
  initial: [],
  on: {
    attachment: (state, { data: { attachment } }) =>
      state.some((item) => item.id === attachment.id)
        ? state.map((item) => (item.id === attachment.id ? attachment : item))
        : [...state, attachment],
    "attachment.removed": (state, { data }) =>
      state.some((item) => item.id === data.id)
        ? state.filter((item) => item.id !== data.id)
        : state,
  },
};

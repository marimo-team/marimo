/* Copyright 2023 Marimo. All rights reserved. */
export const Events = {
  stopPropagation: <E extends Pick<Event, "stopPropagation">>(
    callback?: (evt: E) => void
  ) => {
    return (event: E) => {
      event.stopPropagation();
      if (callback) {
        callback(event);
      }
    };
  },
};

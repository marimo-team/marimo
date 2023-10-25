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
  onEnter: <E extends Pick<KeyboardEvent, "key">>(
    callback?: (evt: E) => void
  ) => {
    return (event: E) => {
      if (event.key === "Enter" && callback) {
        callback(event);
      }
    };
  },
};

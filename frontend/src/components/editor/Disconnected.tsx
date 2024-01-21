/* Copyright 2024 Marimo. All rights reserved. */

export const Disconnected = (props: { reason: string }) => {
  return (
    <div id="Disconnected">
      <p>{props.reason}</p>
    </div>
  );
};

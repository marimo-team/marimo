/* Copyright 2024 Marimo. All rights reserved. */
import { ConnectionStatus, WebSocketState } from "@/core/websocket/types";
import React, { PropsWithChildren } from "react";
import { Disconnected } from "../Disconnected";

interface Props {
  className?: string;
  connection: ConnectionStatus;
}

export const AppHeader: React.FC<PropsWithChildren<Props>> = ({
  connection,
  className,
  children,
}) => {
  return (
    <div className={className}>
      {children}
      {connection.state === WebSocketState.CLOSED && (
        <Disconnected reason={connection.reason} />
      )}
    </div>
  );
};

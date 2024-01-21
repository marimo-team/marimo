/* Copyright 2024 Marimo. All rights reserved. */
import { Server } from "mock-socket";
import { getKernelId } from "../core/kernel/kernel";
import { UUID } from "../utils/uuid";
import { Logger } from "../utils/Logger";

export function createMockServer() {
  const fakeURL = `ws://${
    window.location.host
  }/iosocket?kernel_id=${getKernelId()}&uuid=${UUID}`;
  const mockServer = new Server(fakeURL);

  mockServer.on("connection", (socket) => {
    socket.on("message", (data) => {
      Logger.log("[mock] message", data);
    });
    socket.on("close", () => {
      Logger.log("[mock] close");
    });
  });
}

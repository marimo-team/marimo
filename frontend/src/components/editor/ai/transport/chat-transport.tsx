/* Copyright 2024 Marimo. All rights reserved. */

import {
  DefaultChatTransport,
  type HttpChatTransportInitOptions,
  type UIMessage,
  type UIMessageChunk,
} from "ai";

/**
 * Thin wrapper around the DefaultChatTransport that calls a callback when a chunk is received.
 */
export class StreamingChunkTransport<
  UI_MESSAGE extends UIMessage,
> extends DefaultChatTransport<UI_MESSAGE> {
  constructor(
    options: HttpChatTransportInitOptions<UI_MESSAGE> = {},
    private onChunkReceived: (chunk: UIMessageChunk) => void,
  ) {
    super(options);
  }

  protected override processResponseStream(
    stream: ReadableStream<Uint8Array>,
  ): ReadableStream<UIMessageChunk> {
    const onChunkReceived = this.onChunkReceived;
    return super.processResponseStream(stream).pipeThrough(
      new TransformStream<UIMessageChunk, UIMessageChunk>({
        async transform(chunk, controller) {
          onChunkReceived(chunk);
          controller.enqueue(chunk);
        },
      }),
    );
  }
}

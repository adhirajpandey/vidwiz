import { describe, expect, it } from 'vitest';
import { readSseEvents } from './sse';

function streamChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

describe('readSseEvents', () => {
  it('reassembles events split across transport chunks', async () => {
    const events = [];

    for await (const event of readSseEvents(
      streamChunks([
        'event: update\ndata: {"con',
        'tent":"hello"}\n\ndata: [DONE]\n\n',
      ])
    )) {
      events.push(event);
    }

    expect(events).toStrictEqual([
      { event: 'update', data: '{"content":"hello"}' },
      { data: '[DONE]' },
    ]);
  });

  it('joins multiple data lines and supports CRLF framing', async () => {
    const events = [];

    for await (const event of readSseEvents(
      streamChunks(['event: snapshot\r\ndata: first\r\ndata: second\r\n\r\n'])
    )) {
      events.push(event);
    }

    expect(events).toStrictEqual([
      { event: 'snapshot', data: 'first\nsecond' },
    ]);
  });

  it('supports a CRLF delimiter split across chunks', async () => {
    const events = [];

    for await (const event of readSseEvents(
      streamChunks([
        'event: update\r',
        '\ndata: {"ok":true}\r',
        '\n\r',
        '\n',
      ])
    )) {
      events.push(event);
    }

    expect(events).toStrictEqual([
      { event: 'update', data: '{"ok":true}' },
    ]);
  });

  it('emits a final complete event when the stream closes without a blank line', async () => {
    const events = [];

    for await (const event of readSseEvents(
      streamChunks(['data: {"content":"final"}'])
    )) {
      events.push(event);
    }

    expect(events).toStrictEqual([{ data: '{"content":"final"}' }]);
  });
});

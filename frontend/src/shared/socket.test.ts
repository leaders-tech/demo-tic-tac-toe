/*
This file tests the shared websocket client helper.
Edit this file when websocket client behavior or reconnect rules change.
Copy a test pattern here when you add another small realtime helper.
*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createUserSocket } from "./socket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor() {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.onclose?.();
  }

  emitOpen() {
    this.onopen?.();
  }

  emitMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent<string>);
  }

  emitError() {
    this.onerror?.();
  }
}

describe("createUserSocket", () => {
  const originalWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    globalThis.WebSocket = originalWebSocket;
  });

  it("receives messages and reconnects with backoff that resets after a good connect", () => {
    const onMessage = vi.fn();
    const onStatus = vi.fn();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const socket = createUserSocket({ onMessage, onStatus });
    const first = FakeWebSocket.instances[0];

    socket.send({ type: "lobby.subscribe" });
    first.emitOpen();
    first.emitMessage(JSON.stringify({ type: "ws.ready", user_id: 1, connections: 1 }));
    first.emitError();
    expect(warn).toHaveBeenCalledWith("WebSocket error.");
    first.close();
    vi.advanceTimersByTime(1499);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    const second = FakeWebSocket.instances[1];
    second.close();
    vi.advanceTimersByTime(2999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    const third = FakeWebSocket.instances[2];
    third.emitOpen();
    third.close();
    vi.advanceTimersByTime(1499);
    expect(FakeWebSocket.instances).toHaveLength(3);
    vi.advanceTimersByTime(1);

    expect(onStatus).toHaveBeenCalledWith("connected");
    expect(onMessage).toHaveBeenCalledWith({ type: "ws.ready", user_id: 1, connections: 1 });
    expect(first.sent).toContain(JSON.stringify({ type: "lobby.subscribe" }));
    expect(FakeWebSocket.instances).toHaveLength(4);

    socket.stop();
    warn.mockRestore();
  });
});

/*
This file keeps the small frontend websocket client with reconnect and queued message logic.
Edit this file when websocket connection flow or client-side message handling changes.
Copy this file as a starting point when you add another small websocket client helper.
*/

import type { WsClientMessage, WsMessage } from "./types";
import { getWsUrl } from "./api";

export type SocketStatus = "idle" | "connecting" | "connected" | "disconnected";

type CreateSocketOptions = {
  onMessage: (message: WsMessage) => void;
  onStatus: (status: SocketStatus) => void;
};

export function createUserSocket(options: CreateSocketOptions) {
  let ws: WebSocket | null = null;
  let stopped = false;
  let reconnectTimer: number | null = null;
  let reconnectDelayMs = 1500;
  const pendingMessages: string[] = [];

  const connect = () => {
    options.onStatus("connecting");
    ws = new WebSocket(getWsUrl());
    ws.onopen = () => {
      reconnectDelayMs = 1500;
      while (pendingMessages.length > 0) {
        ws?.send(pendingMessages.shift() ?? "");
      }
      options.onStatus("connected");
    };
    ws.onmessage = (event) => options.onMessage(JSON.parse(event.data) as WsMessage);
    ws.onerror = () => console.warn("WebSocket error.");
    ws.onclose = () => {
      options.onStatus("disconnected");
      if (!stopped) {
        reconnectTimer = window.setTimeout(connect, reconnectDelayMs);
        reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30000);
      }
    };
  };

  connect();

  return {
    send(message: WsClientMessage) {
      const payload = JSON.stringify(message);
      if (ws !== null && ws.readyState === WebSocket.OPEN) {
        ws.send(payload);
        return;
      }
      pendingMessages.push(payload);
    },
    stop() {
      stopped = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      ws?.close();
    },
  };
}

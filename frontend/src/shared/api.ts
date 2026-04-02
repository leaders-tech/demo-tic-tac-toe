/*
This file sends frontend JSON requests to the backend and builds the websocket base URL.
Edit this file when backend URL rules, shared fetch behavior, or API error parsing changes.
Copy the helper pattern here when you add another shared browser API helper.
*/

import type { ApiResponse } from "./types";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function getBackendBaseUrl(): string {
  const configured = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  return window.location.origin;
}

const baseUrl = getBackendBaseUrl();

async function readApiPayload<T>(response: Response): Promise<ApiResponse<T>> {
  const text = await response.text();
  if (!text) {
    throw new ApiError(response.status, "empty_response", "Server returned an empty response.");
  }

  try {
    return JSON.parse(text) as ApiResponse<T>;
  } catch {
    throw new ApiError(response.status, "invalid_json", "Server returned invalid JSON.");
  }
}

export async function postJson<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const payload = await readApiPayload<T>(response);
  if (!payload.ok) {
    throw new ApiError(response.status, payload.error.code, payload.error.message);
  }
  return payload.data;
}

export function getWsUrl(): string {
  const wsBase = baseUrl.replace(/^http/, "ws");
  return `${wsBase}/ws`;
}

/*
This file tests the lobby page sections, actions, and live lobby updates.
Edit this file when lobby page UI states or socket update behavior changes.
Copy a test pattern here when you add another page test with mocked API and sockets.
*/

import "@testing-library/jest-dom/vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LobbyPage } from "./LobbyPage";
import { AuthContext } from "../app/auth";
import type { LobbySnapshot, User, WsMessage } from "../shared/types";

const postJson = vi.fn();
const socketSend = vi.fn();
const socketStop = vi.fn();
let socketOptions: {
  onMessage: (message: WsMessage) => void;
  onStatus: (status: "idle" | "connecting" | "connected" | "disconnected") => void;
} | null = null;

vi.mock("../shared/api", () => ({
  postJson: (...args: unknown[]) => postJson(...args),
}));

vi.mock("../shared/socket", () => ({
  createUserSocket: (options: typeof socketOptions) => {
    socketOptions = options;
    return {
      send: socketSend,
      stop: socketStop,
    };
  },
}));

const userValue: User = {
  id: 2,
  username: "user",
  is_admin: false,
  created_at: "2026-03-06T10:00:00+00:00",
  updated_at: "2026-03-06T10:00:00+00:00",
};

function renderLobby() {
  return render(
    <MemoryRouter>
      <AuthContext.Provider
        value={{
          user: userValue,
          loading: false,
          login: vi.fn(),
          logout: vi.fn(),
          reloadUser: vi.fn(),
        }}
      >
        <LobbyPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("LobbyPage", () => {
  it("renders lobby sections and action visibility from the snapshot", async () => {
    const snapshot: LobbySnapshot = {
      waiting_games: [
        {
          id: 1,
          status: "waiting",
          starter_symbol: "X",
          turn_symbol: "X",
          winner_symbol: null,
          finish_reason: null,
          disconnect_deadline_at: null,
          created_at: "",
          updated_at: "",
          viewer_role: "spectator",
          is_spectator: true,
          can_join: true,
          can_cancel: false,
          players: {
            X: { id: 10, username: "alpha", connected: true },
            O: null,
          },
        },
      ],
      active_games: [
        {
          id: 2,
          status: "active",
          starter_symbol: "X",
          turn_symbol: "O",
          winner_symbol: null,
          finish_reason: null,
          disconnect_deadline_at: null,
          created_at: "",
          updated_at: "",
          viewer_role: "spectator",
          is_spectator: true,
          can_join: false,
          can_cancel: false,
          players: {
            X: { id: 10, username: "alpha", connected: true },
            O: { id: 11, username: "beta", connected: false },
          },
        },
      ],
      finished_games: [
        {
          id: 3,
          status: "finished",
          starter_symbol: "X",
          turn_symbol: null,
          winner_symbol: "X",
          finish_reason: "line",
          disconnect_deadline_at: null,
          created_at: "",
          updated_at: "",
          viewer_role: "spectator",
          is_spectator: true,
          can_join: false,
          can_cancel: false,
          players: {
            X: { id: 10, username: "alpha", connected: true },
            O: { id: 11, username: "beta", connected: true },
          },
        },
      ],
    };
    postJson.mockResolvedValue(snapshot);

    renderLobby();

    expect(await screen.findByRole("heading", { name: "Waiting Games" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Join game" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Watch game" })).toHaveLength(2);
    expect(screen.getByText("Winner: X")).toBeInTheDocument();
    expect(socketSend).toHaveBeenCalledWith({ type: "lobby.subscribe" });
  });

  it("updates the lobby when a socket snapshot arrives", async () => {
    postJson.mockResolvedValue({
      waiting_games: [],
      active_games: [],
      finished_games: [],
    } satisfies LobbySnapshot);

    renderLobby();
    await screen.findByText("No one is waiting right now. Create a game to start.");

    await act(async () => {
      socketOptions?.onMessage({
        type: "lobby.snapshot",
        lobby: {
          waiting_games: [
            {
              id: 12,
              status: "waiting",
              starter_symbol: "X",
              turn_symbol: "X",
              winner_symbol: null,
              finish_reason: null,
              disconnect_deadline_at: null,
              created_at: "",
              updated_at: "",
              viewer_role: "spectator",
              is_spectator: true,
              can_join: true,
              can_cancel: false,
              players: {
                X: { id: 15, username: "fresh", connected: true },
                O: null,
              },
            },
          ],
          active_games: [],
          finished_games: [],
        },
      });
    });

    expect(screen.getByText("fresh vs Waiting player")).toBeInTheDocument();
  });
});

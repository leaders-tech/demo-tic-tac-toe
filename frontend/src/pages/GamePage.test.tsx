/*
This file tests the game page board, spectator/player controls, and rematch UI.
Edit this file when game page states, move controls, or socket updates change.
Copy a test pattern here when you add another detailed page test.
*/

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { GamePage } from "./GamePage";
import { AuthContext } from "../app/auth";
import type { GameSnapshot, User, WsMessage } from "../shared/types";

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

function makeBoard(topSymbol: "X" | "O"): GameSnapshot["board"] {
  return [
    [
      {
        row_index: 0,
        col_index: 0,
        stack: [
          { symbol: "X", user_id: 2, size: "small", row_index: 0, col_index: 0, turn_number: 1 },
          { symbol: topSymbol, user_id: 3, size: "large", row_index: 0, col_index: 0, turn_number: 2 },
        ],
        top_piece: { symbol: topSymbol, user_id: 3, size: "large", row_index: 0, col_index: 0, turn_number: 2 },
        available_sizes: [],
      },
      {
        row_index: 0,
        col_index: 1,
        stack: [],
        top_piece: null,
        available_sizes: ["small", "medium", "large"],
      },
      {
        row_index: 0,
        col_index: 2,
        stack: [],
        top_piece: null,
        available_sizes: ["small", "medium", "large"],
      },
    ],
    [
      { row_index: 1, col_index: 0, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
      { row_index: 1, col_index: 1, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
      { row_index: 1, col_index: 2, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
    ],
    [
      { row_index: 2, col_index: 0, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
      { row_index: 2, col_index: 1, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
      { row_index: 2, col_index: 2, stack: [], top_piece: null, available_sizes: ["small", "medium", "large"] },
    ],
  ];
}

function renderGame(snapshot: GameSnapshot) {
  postJson.mockResolvedValue(snapshot);
  return render(
    <MemoryRouter initialEntries={[`/games/${snapshot.id}`]}>
      <AuthContext.Provider
        value={{
          user: userValue,
          loading: false,
          login: vi.fn(),
          logout: vi.fn(),
          reloadUser: vi.fn(),
        }}
      >
        <Routes>
          <Route element={<GamePage />} path="/games/:gameId" />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("GamePage", () => {
  it("shows stacked cells and spectator join controls", async () => {
    renderGame({
      id: 12,
      status: "waiting",
      starter_symbol: "X",
      turn_symbol: "X",
      winner_symbol: null,
      finish_reason: null,
      forfeit_user_id: null,
      disconnect_deadline_at: null,
      created_at: "",
      updated_at: "",
      viewer_role: "spectator",
      is_spectator: true,
      can_move: false,
      can_cancel: false,
      can_rematch: false,
      next_game_id: null,
      players: {
        X: { id: 2, username: "user", connected: true },
        O: null,
      },
      rematch: { x_ready: false, o_ready: false },
      remaining_pieces: {
        X: { small: 3, medium: 3, large: 3 },
        O: { small: 3, medium: 3, large: 3 },
      },
      board: makeBoard("O"),
      move_count: 2,
      legal_move_exists_for_turn: true,
    });

    expect(await screen.findByRole("button", { name: "Join as O" })).toBeInTheDocument();
    expect(screen.getByText("X-small, O-large")).toBeInTheDocument();
    expect(socketSend).toHaveBeenCalledWith({ type: "game.subscribe", game_id: 12 });
  });

  it("shows rematch controls and reconnect countdown for finished games", async () => {
    renderGame({
      id: 33,
      status: "finished",
      starter_symbol: "X",
      turn_symbol: null,
      winner_symbol: "X",
      finish_reason: "forfeit",
      forfeit_user_id: 3,
      disconnect_deadline_at: new Date(Date.now() + 20_000).toISOString(),
      created_at: "",
      updated_at: "",
      viewer_role: "X",
      is_spectator: false,
      can_move: false,
      can_cancel: false,
      can_rematch: true,
      next_game_id: 44,
      players: {
        X: { id: 2, username: "user", connected: true },
        O: { id: 3, username: "beta", connected: false },
      },
      rematch: { x_ready: true, o_ready: false },
      remaining_pieces: {
        X: { small: 1, medium: 2, large: 3 },
        O: { small: 3, medium: 1, large: 0 },
      },
      board: makeBoard("X"),
      move_count: 8,
      legal_move_exists_for_turn: false,
    });

    expect(await screen.findByRole("button", { name: "Play again" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open rematch" })).toBeInTheDocument();
    expect(screen.getByText(/Reconnect timer:/)).toBeInTheDocument();
  });
});

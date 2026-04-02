/*
This file keeps the shared frontend types for auth, games, API results, and websocket messages.
Edit this file when backend JSON shapes or websocket message shapes change.
Copy a type pattern here when you add another shared API or websocket type.
*/

export type User = {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
};

export type Note = {
  id: number;
  user_id: number;
  text: string;
  created_at: string;
  updated_at: string;
};

export type ApiOk<T> = {
  ok: true;
  data: T;
};

export type ApiFail = {
  ok: false;
  error: {
    code: string;
    message: string;
  };
};

export type ApiResponse<T> = ApiOk<T> | ApiFail;

export type GameSymbol = "X" | "O";

export type GameSize = "small" | "medium" | "large";

export type GamePlayer = {
  id: number;
  username: string;
  connected: boolean;
};

export type GamePiece = {
  symbol: GameSymbol;
  user_id: number;
  size: GameSize;
  row_index: number;
  col_index: number;
  turn_number: number;
};

export type GameCell = {
  row_index: number;
  col_index: number;
  stack: GamePiece[];
  top_piece: GamePiece | null;
  available_sizes: GameSize[];
};

export type GameSummary = {
  id: number;
  status: "waiting" | "active" | "finished";
  starter_symbol: GameSymbol;
  turn_symbol: GameSymbol | null;
  winner_symbol: GameSymbol | null;
  finish_reason: "line" | "no_moves" | "forfeit" | null;
  disconnect_deadline_at: string | null;
  created_at: string;
  updated_at: string;
  viewer_role: GameSymbol | "spectator";
  is_spectator: boolean;
  can_join: boolean;
  can_cancel: boolean;
  players: {
    X: GamePlayer;
    O: GamePlayer | null;
  };
};

export type LobbySnapshot = {
  waiting_games: GameSummary[];
  active_games: GameSummary[];
  finished_games: GameSummary[];
};

export type GameSnapshot = {
  id: number;
  status: "waiting" | "active" | "finished";
  starter_symbol: GameSymbol;
  turn_symbol: GameSymbol | null;
  winner_symbol: GameSymbol | null;
  finish_reason: "line" | "no_moves" | "forfeit" | null;
  forfeit_user_id: number | null;
  disconnect_deadline_at: string | null;
  created_at: string;
  updated_at: string;
  viewer_role: GameSymbol | "spectator";
  is_spectator: boolean;
  can_move: boolean;
  can_cancel: boolean;
  can_rematch: boolean;
  next_game_id: number | null;
  players: {
    X: GamePlayer;
    O: GamePlayer | null;
  };
  rematch: {
    x_ready: boolean;
    o_ready: boolean;
  };
  remaining_pieces: {
    X: Record<GameSize, number>;
    O: Record<GameSize, number>;
  };
  board: GameCell[][];
  move_count: number;
  legal_move_exists_for_turn: boolean;
};

export type WsClientMessage = { type: "ping" } | { type: "lobby.subscribe" } | { type: "game.subscribe"; game_id: number };

export type WsMessage =
  | { type: "ws.ready"; user_id: number; connections: number }
  | { type: "pong" }
  | { type: "notes.changed"; note?: Note; note_id?: number }
  | { type: "lobby.snapshot"; lobby: LobbySnapshot }
  | { type: "game.snapshot"; game: GameSnapshot }
  | { type: "error"; code: string; message: string };

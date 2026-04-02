/*
This file shows one game board, the live game state, and player actions.
Edit this file when game page layout, move actions, or live game updates change.
Copy this file as a starting point when you add another realtime detail page.
*/

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../app/auth";
import { postJson } from "../shared/api";
import { createUserSocket, type SocketStatus } from "../shared/socket";
import type { GameCell, GamePiece, GameSize, GameSnapshot, WsMessage } from "../shared/types";

const sizePixels: Record<GameSize, number> = {
  small: 38,
  medium: 58,
  large: 80,
};

function sizeLabel(size: GameSize) {
  if (size === "small") {
    return "Small";
  }
  if (size === "medium") {
    return "Medium";
  }
  return "Large";
}

function finishText(game: GameSnapshot) {
  if (game.status === "waiting") {
    return "Waiting for the second player to join.";
  }
  if (game.status === "active") {
    return `Turn: ${game.turn_symbol}`;
  }
  if (game.finish_reason === "forfeit") {
    return `Winner: ${game.winner_symbol} by forfeit`;
  }
  if (game.finish_reason === "no_moves") {
    return `Winner: ${game.winner_symbol} because the other player had no legal move`;
  }
  return `Winner: ${game.winner_symbol}`;
}

function countdownText(deadline: string | null, nowMs: number) {
  if (!deadline) {
    return "";
  }
  const seconds = Math.max(0, Math.ceil((new Date(deadline).getTime() - nowMs) / 1000));
  return `Reconnect timer: ${seconds}s`;
}

function PieceShape({ piece }: { piece: GamePiece }) {
  const size = sizePixels[piece.size];
  const color = piece.symbol === "X" ? "#c2410c" : "#0369a1";
  const commonStyle = {
    width: `${size}px`,
    height: `${size}px`,
  };

  if (piece.symbol === "O") {
    return <div className="rounded-full border-[6px]" style={{ ...commonStyle, borderColor: color }} />;
  }

  return (
    <div className="relative" style={commonStyle}>
      <div className="absolute left-1/2 top-0 h-full w-[6px] -translate-x-1/2 rotate-45 rounded-full" style={{ backgroundColor: color }} />
      <div className="absolute left-1/2 top-0 h-full w-[6px] -translate-x-1/2 -rotate-45 rounded-full" style={{ backgroundColor: color }} />
    </div>
  );
}

function CellButton({
  cell,
  selectedSize,
  disabled,
  onMove,
}: {
  cell: GameCell;
  selectedSize: GameSize;
  disabled: boolean;
  onMove: (rowIndex: number, colIndex: number) => Promise<void>;
}) {
  const canUseSelectedSize = cell.available_sizes.includes(selectedSize);
  const labelStack = cell.stack.map((piece) => `${piece.symbol}-${piece.size}`).join(", ");

  return (
    <button
      aria-label={`Cell ${cell.row_index + 1}-${cell.col_index + 1}`}
      className={`relative flex aspect-square min-h-28 items-center justify-center rounded-[1.6rem] border border-slate-300 bg-white shadow-inner transition ${
        disabled || !canUseSelectedSize ? "cursor-not-allowed opacity-70" : "hover:border-amber-400 hover:bg-amber-50"
      }`}
      disabled={disabled || !canUseSelectedSize}
      onClick={() => void onMove(cell.row_index, cell.col_index)}
      title={labelStack || "Empty cell"}
    >
      <div className="absolute inset-3 rounded-[1.25rem] border border-dashed border-slate-200" />
      <div className="relative flex items-center justify-center">
        {cell.stack.map((piece, index) => (
          <div className="absolute" key={`${piece.symbol}-${piece.turn_number}-${index}`}>
            <PieceShape piece={piece} />
          </div>
        ))}
      </div>
      <div className="absolute bottom-2 left-2 right-2 text-center text-[11px] font-medium text-slate-500">
        {labelStack || "Empty"}
      </div>
    </button>
  );
}

function InventoryPanel({
  game,
  selectedSize,
  onSelect,
}: {
  game: GameSnapshot;
  selectedSize: GameSize;
  onSelect: (size: GameSize) => void;
}) {
  const symbol = game.viewer_role === "spectator" ? game.turn_symbol ?? "X" : game.viewer_role;
  const remaining = game.remaining_pieces[symbol];

  return (
    <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-lg shadow-slate-200/50">
      <h3 className="text-lg font-semibold text-slate-900">Your move tray</h3>
      <p className="mt-1 text-sm text-slate-600">
        {game.viewer_role === "spectator" ? "Spectators cannot move. This tray shows the current turn piece counts." : "Choose a size, then click a board cell."}
      </p>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {(["small", "medium", "large"] as GameSize[]).map((size) => (
          <button
            className={`rounded-[1.6rem] border px-3 py-4 text-left ${
              selectedSize === size ? "border-amber-500 bg-amber-50" : "border-slate-200 bg-slate-50"
            } disabled:cursor-not-allowed disabled:opacity-60`}
            disabled={game.viewer_role === "spectator" || remaining[size] === 0}
            key={size}
            onClick={() => onSelect(size)}
          >
            <p className="text-sm font-semibold text-slate-900">{sizeLabel(size)}</p>
            <p className="mt-1 text-xs text-slate-600">Left: {remaining[size]}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

export function GamePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const params = useParams();
  const gameId = Number(params.gameId ?? "");
  const [game, setGame] = useState<GameSnapshot | null>(null);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("idle");
  const [selectedSize, setSelectedSize] = useState<GameSize>("small");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!Number.isInteger(gameId) || !user) {
      return;
    }

    let active = true;
    const loadGame = async () => {
      try {
        const data = await postJson<GameSnapshot>("/api/games/state", { game_id: gameId });
        if (active) {
          setGame(data);
          setError("");
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load the game.");
        }
      }
    };

    void loadGame();

    const socket = createUserSocket({
      onMessage(message: WsMessage) {
        if (message.type === "game.snapshot" && message.game.id === gameId) {
          setGame(message.game);
          setError("");
        }
        if (message.type === "error") {
          setError(message.message);
        }
      },
      onStatus(status) {
        setSocketStatus(status);
      },
    });
    socket.send({ type: "game.subscribe", game_id: gameId });

    return () => {
      active = false;
      socket.stop();
    };
  }, [gameId, user]);

  useEffect(() => {
    if (!game?.disconnect_deadline_at) {
      return;
    }
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [game?.disconnect_deadline_at]);

  const viewerRemaining = useMemo(() => {
    if (!game || game.viewer_role === "spectator") {
      return null;
    }
    return game.remaining_pieces[game.viewer_role];
  }, [game]);

  useEffect(() => {
    if (!viewerRemaining) {
      return;
    }
    if (viewerRemaining[selectedSize] > 0) {
      return;
    }
    const nextSize = (["small", "medium", "large"] as GameSize[]).find((size) => viewerRemaining[size] > 0);
    if (nextSize) {
      setSelectedSize(nextSize);
    }
  }, [selectedSize, viewerRemaining]);

  if (!user) {
    return null;
  }

  if (!Number.isInteger(gameId)) {
    return <p className="rounded-[2rem] bg-rose-100 px-4 py-3 text-rose-800">Game id is not valid.</p>;
  }

  const move = async (rowIndex: number, colIndex: number) => {
    setBusy(true);
    setError("");
    try {
      await postJson<{ accepted: boolean; game_id: number }>("/api/games/move", {
        game_id: gameId,
        row_index: rowIndex,
        col_index: colIndex,
        size: selectedSize,
      });
    } catch (moveError) {
      setError(moveError instanceof Error ? moveError.message : "Could not make the move.");
    } finally {
      setBusy(false);
    }
  };

  const joinGame = async () => {
    setBusy(true);
    setError("");
    try {
      await postJson<{ game_id: number }>("/api/games/join", { game_id: gameId });
    } catch (joinError) {
      setError(joinError instanceof Error ? joinError.message : "Could not join the game.");
    } finally {
      setBusy(false);
    }
  };

  const cancelGame = async () => {
    setBusy(true);
    setError("");
    try {
      await postJson<{ cancelled: boolean; game_id: number }>("/api/games/cancel", { game_id: gameId });
      navigate("/lobby");
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Could not cancel the game.");
    } finally {
      setBusy(false);
    }
  };

  const requestRematch = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await postJson<{ game_id: number; next_game_id: number | null }>("/api/games/rematch", { game_id: gameId });
      if (data.next_game_id) {
        navigate(`/games/${data.next_game_id}`);
      }
    } catch (rematchError) {
      setError(rematchError instanceof Error ? rematchError.message : "Could not request a rematch.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Game #{gameId}</p>
          <h2 className="mt-2 text-3xl font-semibold text-slate-900">{game ? finishText(game) : "Loading game..."}</h2>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800" to="/lobby">
            Back to lobby
          </Link>
          {game?.next_game_id ? (
            <Link className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white" to={`/games/${game.next_game_id}`}>
              Open rematch
            </Link>
          ) : null}
        </div>
      </div>

      {error ? <p className="rounded-[2rem] bg-rose-100 px-4 py-3 text-rose-800">{error}</p> : null}

      {game ? (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            <div className="rounded-[2rem] bg-white/90 p-6 shadow-xl shadow-slate-200/60">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-slate-600">X: {game.players.X.username}</p>
                  <p className="mt-1 text-sm text-slate-600">O: {game.players.O?.username ?? "Waiting player"}</p>
                  <p className="mt-3 text-sm text-slate-500">Socket: {socketStatus}</p>
                  {game.disconnect_deadline_at ? <p className="mt-1 text-sm font-medium text-rose-700">{countdownText(game.disconnect_deadline_at, nowMs)}</p> : null}
                </div>
                <div className="rounded-[1.6rem] bg-slate-100 px-4 py-3 text-sm text-slate-700">
                  <p>Role: {game.viewer_role === "spectator" ? "spectator" : `player ${game.viewer_role}`}</p>
                  <p className="mt-1">Moves played: {game.move_count}</p>
                </div>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {game.board.flat().map((cell) => (
                  <CellButton cell={cell} disabled={busy || !game.can_move} key={`${cell.row_index}-${cell.col_index}`} onMove={move} selectedSize={selectedSize} />
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-6 shadow-lg shadow-slate-200/50">
              <h3 className="text-lg font-semibold text-slate-900">Stack guide</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                Each cell shows every piece in stack order. The bigger visible piece is the one that counts for winning. A move is legal only if your chosen piece is larger than the top visible piece in that cell.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {(["small", "medium", "large"] as GameSize[]).map((size) => (
                  <div className="rounded-[1.6rem] bg-slate-50 p-4" key={size}>
                    <p className="text-sm font-semibold text-slate-900">{sizeLabel(size)}</p>
                    <p className="mt-1 text-xs text-slate-600">X left: {game.remaining_pieces.X[size]}</p>
                    <p className="text-xs text-slate-600">O left: {game.remaining_pieces.O[size]}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <InventoryPanel game={game} onSelect={setSelectedSize} selectedSize={selectedSize} />

            <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-lg shadow-slate-200/50">
              <h3 className="text-lg font-semibold text-slate-900">Actions</h3>
              <div className="mt-4 flex flex-wrap gap-3">
                {game.status === "waiting" && game.can_cancel ? (
                  <button className="rounded-full bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} onClick={() => void cancelGame()}>
                    Cancel waiting game
                  </button>
                ) : null}
                {game.status === "waiting" && game.viewer_role === "spectator" ? (
                  <button className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} onClick={() => void joinGame()}>
                    Join as O
                  </button>
                ) : null}
                {game.status === "finished" && game.can_rematch ? (
                  <button className="rounded-full bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60" disabled={busy} onClick={() => void requestRematch()}>
                    Play again
                  </button>
                ) : null}
              </div>
              <div className="mt-4 rounded-[1.6rem] bg-slate-50 p-4 text-sm text-slate-700">
                <p>Starter: {game.starter_symbol}</p>
                <p className="mt-1">Rematch ready: X {game.rematch.x_ready ? "yes" : "no"}, O {game.rematch.o_ready ? "yes" : "no"}</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

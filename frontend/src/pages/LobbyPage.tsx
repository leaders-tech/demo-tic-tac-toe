/*
This file shows the logged-in lobby with waiting, active, and recent finished games.
Edit this file when lobby layout, lobby actions, or live lobby updates change.
Copy this file as a starting point when you add another logged-in realtime page.
*/

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../app/auth";
import { postJson } from "../shared/api";
import { createUserSocket, type SocketStatus } from "../shared/socket";
import type { GameSummary, LobbySnapshot, WsMessage } from "../shared/types";

function formatStatus(game: GameSummary) {
  if (game.status === "waiting") {
    return "Waiting for player";
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

function GameCard({
  game,
  onJoin,
  onCancel,
}: {
  game: GameSummary;
  onJoin: (gameId: number) => Promise<void>;
  onCancel: (gameId: number) => Promise<void>;
}) {
  return (
    <article className="rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-lg shadow-slate-200/50">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Game #{game.id}</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">
            {game.players.X.username} vs {game.players.O?.username ?? "Waiting player"}
          </h3>
          <p className="mt-1 text-sm text-slate-600">{formatStatus(game)}</p>
        </div>
        <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">{game.status}</div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm text-slate-700">
        <span className="rounded-full bg-amber-100 px-3 py-1">X: {game.players.X.connected ? "online" : "offline"}</span>
        <span className="rounded-full bg-sky-100 px-3 py-1">O: {game.players.O?.connected ? "online" : "offline"}</span>
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50" to={`/games/${game.id}`}>
          {game.status === "active" || game.status === "finished" ? "Watch game" : "Open game"}
        </Link>
        {game.can_join ? (
          <button className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white" onClick={() => void onJoin(game.id)}>
            Join game
          </button>
        ) : null}
        {game.can_cancel ? (
          <button className="rounded-full bg-rose-600 px-4 py-2 text-sm font-semibold text-white" onClick={() => void onCancel(game.id)}>
            Cancel
          </button>
        ) : null}
      </div>
    </article>
  );
}

function GameSection({
  title,
  description,
  games,
  emptyText,
  onJoin,
  onCancel,
}: {
  title: string;
  description: string;
  games: GameSummary[];
  emptyText: string;
  onJoin: (gameId: number) => Promise<void>;
  onCancel: (gameId: number) => Promise<void>;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-600">{description}</p>
      </div>
      {games.length === 0 ? <p className="rounded-[2rem] border border-dashed border-slate-300 bg-white/70 p-6 text-slate-600">{emptyText}</p> : null}
      <div className="grid gap-4">
        {games.map((game) => (
          <GameCard game={game} key={game.id} onCancel={onCancel} onJoin={onJoin} />
        ))}
      </div>
    </section>
  );
}

export function LobbyPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [lobby, setLobby] = useState<LobbySnapshot | null>(null);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("idle");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) {
      return;
    }

    let active = true;
    const loadLobby = async () => {
      try {
        const data = await postJson<LobbySnapshot>("/api/games/lobby");
        if (active) {
          setLobby(data);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load the lobby.");
        }
      }
    };

    void loadLobby();

    const socket = createUserSocket({
      onMessage(message: WsMessage) {
        if (message.type === "lobby.snapshot") {
          setLobby(message.lobby);
          setError("");
        }
      },
      onStatus(status) {
        setSocketStatus(status);
      },
    });
    socket.send({ type: "lobby.subscribe" });

    return () => {
      active = false;
      socket.stop();
    };
  }, [user]);

  if (!user) {
    return null;
  }

  const createGame = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await postJson<{ game_id: number }>("/api/games/create");
      navigate(`/games/${data.game_id}`);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Could not create a game.");
    } finally {
      setBusy(false);
    }
  };

  const joinGame = async (gameId: number) => {
    setBusy(true);
    setError("");
    try {
      const data = await postJson<{ game_id: number }>("/api/games/join", { game_id: gameId });
      navigate(`/games/${data.game_id}`);
    } catch (joinError) {
      setError(joinError instanceof Error ? joinError.message : "Could not join the game.");
    } finally {
      setBusy(false);
    }
  };

  const cancelGame = async (gameId: number) => {
    setBusy(true);
    setError("");
    try {
      await postJson<{ cancelled: boolean; game_id: number }>("/api/games/cancel", { game_id: gameId });
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Could not cancel the game.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] bg-slate-900 px-8 py-8 text-white shadow-2xl shadow-slate-900/20">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.25em] text-amber-300">Layered Tic-Tac-Toe Lobby</p>
            <h2 className="mt-2 text-4xl font-semibold leading-tight">Play live games on a 3 by 3 board with stackable pieces.</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-200">
              Logged in as <strong>{user.username}</strong>. Each player has three small, three medium, and three large pieces. You can cover any smaller visible piece with a larger one.
            </p>
          </div>
          <div className="rounded-[2rem] bg-white/10 px-4 py-3 text-sm text-slate-100">
            <p>Socket: {socketStatus}</p>
            <p className="mt-1">Signed in as {user.is_admin ? "admin" : "player"}</p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="rounded-full bg-amber-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60" disabled={busy} onClick={() => void createGame()}>
            {busy ? "Working..." : "Create new game"}
          </button>
          <Link className="rounded-full border border-white/20 px-5 py-3 font-medium text-white" to="/">
            Read the rules
          </Link>
        </div>
        {error ? <p className="mt-4 rounded-[2rem] bg-rose-100 px-4 py-3 text-sm text-rose-800">{error}</p> : null}
      </div>

      <GameSection
        description="Anyone logged in can join a waiting game unless they created it."
        emptyText="No one is waiting right now. Create a game to start."
        games={lobby?.waiting_games ?? []}
        onCancel={cancelGame}
        onJoin={joinGame}
        title="Waiting Games"
      />
      <GameSection
        description="Active games are live. Players can move. Everyone else can watch."
        emptyText="No active games yet."
        games={lobby?.active_games ?? []}
        onCancel={cancelGame}
        onJoin={joinGame}
        title="Active Games"
      />
      <GameSection
        description="Recent results stay visible here so other users can open and review them."
        emptyText="No finished games yet."
        games={lobby?.finished_games ?? []}
        onCancel={cancelGame}
        onJoin={joinGame}
        title="Recent Results"
      />
    </section>
  );
}

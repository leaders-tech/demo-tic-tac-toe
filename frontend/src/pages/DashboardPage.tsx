/*
This file shows the logged-in dashboard and connects the notes panel to the websocket.
Edit this file when dashboard layout or logged-in live updates change.
Copy this file as a starting point when you add another logged-in page.
*/

import { useEffect, useState } from "react";
import { useAuth } from "../app/auth";
import { createUserSocket, type SocketStatus } from "../shared/socket";
import type { WsMessage } from "../shared/types";
import { NotesPanel } from "../features/notes/NotesPanel";

export function DashboardPage() {
  const { user } = useAuth();
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("idle");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!user) {
      return;
    }
    const socket = createUserSocket({
      onMessage(message: WsMessage) {
        if (message.type === "notes.changed") {
          setRefreshKey((current) => current + 1);
        }
      },
      onStatus(status) {
        setSocketStatus(status);
      },
    });
    return () => socket.stop();
  }, [user]);

  if (!user) {
    return null;
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-sky-200 bg-sky-50/80 p-6">
        <h2 className="text-2xl font-semibold text-slate-900">Dashboard</h2>
        <p className="mt-2 text-slate-700">
          Logged in as <strong>{user.username}</strong>. Role: {user.is_admin ? "admin" : "user"}.
        </p>
      </div>
      <NotesPanel refreshKey={refreshKey} socketStatus={socketStatus} />
    </section>
  );
}

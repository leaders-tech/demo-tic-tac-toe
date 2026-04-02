/*
This file shows the admin-only page and loads the simple user list.
Edit this file when admin page UI or admin-only API behavior changes.
Copy this file as a starting point when you add another admin-only page.
*/

import { useEffect, useState } from "react";
import { postJson } from "../shared/api";
import type { User } from "../shared/types";

export function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    postJson<{ users: User[] }>("/admin/users/list")
      .then((data) => setUsers(data.users))
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Could not load users."));
  }, []);

  return (
    <section className="rounded-3xl border border-slate-200/80 bg-white/90 p-6 shadow-lg shadow-slate-200/70">
      <h2 className="text-2xl font-semibold text-slate-900">Admin page</h2>
      <p className="mt-2 text-slate-600">This page shows a simple protected admin-only endpoint.</p>
      {error ? <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="mt-5 space-y-3">
        {users.map((user) => (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" key={user.id}>
            <span className="font-medium text-slate-900">{user.username}</span>
            <span className="ml-2 text-sm text-slate-600">{user.is_admin ? "admin" : "user"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

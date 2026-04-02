/*
This file shows the login page and posts username and password to the backend.
Edit this file when login UI, login errors, or login redirect behavior changes.
Copy this file as a starting point when you add another simple form page.
*/

import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../app/auth";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) {
    return <Navigate to="/lobby" replace />;
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      navigate("/lobby");
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "Login failed.";
      setError(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mx-auto max-w-md rounded-3xl border border-slate-200/80 bg-white/85 p-8 shadow-lg shadow-slate-200/70">
      <h2 className="text-2xl font-semibold text-slate-900">Login</h2>
      <p className="mt-2 text-sm text-slate-600">In dev mode, example users are shown on the home page. Enter them here yourself if you want to test login.</p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">Username</span>
          <input
            className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3"
            onChange={(event) => setUsername(event.target.value)}
            value={username}
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">Password</span>
          <input
            className="w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </label>
        {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
        <button className="w-full rounded-2xl bg-slate-900 px-4 py-3 font-semibold text-white" disabled={busy} type="submit">
          {busy ? "Logging in..." : "Login"}
        </button>
      </form>
    </section>
  );
}

/*
This file shows the login page and supports local-password or OIDC sign-in.
Edit this file when login UI, login errors, OIDC availability, or login redirect behavior changes.
Copy this file as a starting point when you add another simple form page.
*/

import { FormEvent, useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../app/auth";
import { getBackendBaseUrl, postJson } from "../shared/api";
import type { AuthOptions } from "../shared/types";


function readLoginError(searchParams: URLSearchParams): string {
  const errorCode = searchParams.get("error");
  if (errorCode === "oidc_state_invalid") {
    return "Leaders Auth login expired or came back with the wrong state. Please try again.";
  }
  if (errorCode === "oidc_login_failed") {
    return "Leaders Auth login failed. Please try again.";
  }
  return "";
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(() => readLoginError(searchParams));
  const [busy, setBusy] = useState(false);
  const [authOptions, setAuthOptions] = useState<AuthOptions>({ oidc_enabled: false, oidc_login_url: null });

  useEffect(() => {
    setError(readLoginError(searchParams));
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    postJson<AuthOptions>("/auth/options")
      .then((data) => {
        if (!cancelled) {
          setAuthOptions(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAuthOptions({ oidc_enabled: false, oidc_login_url: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const oidcLoginUrl = authOptions.oidc_login_url ? `${getBackendBaseUrl()}${authOptions.oidc_login_url}` : null;

  return (
    <section className="mx-auto max-w-md rounded-3xl border border-slate-200/80 bg-white/85 p-8 shadow-lg shadow-slate-200/70">
      <h2 className="text-2xl font-semibold text-slate-900">Login</h2>
      <p className="mt-2 text-sm text-slate-600">You can log in with a local username and password, or use Leaders Auth when it is enabled for this app.</p>
      {authOptions.oidc_enabled && oidcLoginUrl ? (
        <div className="mt-6">
          <a
            className="block w-full rounded-2xl bg-amber-400 px-4 py-3 text-center font-semibold text-slate-950"
            href={oidcLoginUrl}
          >
            Login with Leaders Auth
          </a>
        </div>
      ) : null}
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
          {busy ? "Logging in..." : "Login with password"}
        </button>
      </form>
    </section>
  );
}

/*
This file keeps the frontend auth state, login helpers, and session loading logic.
Edit this file when login, logout, refresh, or current-user browser behavior changes.
Copy the provider and hook pattern here when you add another small shared frontend context.
*/

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, postJson } from "../shared/api";
import type { User } from "../shared/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadCurrentUser(): Promise<User | null> {
  try {
    const data = await postJson<{ user: User }>("/auth/me");
    return data.user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      try {
        await postJson<{ user: User }>("/auth/refresh");
        const refreshed = await postJson<{ user: User }>("/auth/me");
        return refreshed.user;
      } catch {
        return null;
      }
    }
    throw error;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(username: string, password: string) {
        const data = await postJson<{ user: User }>("/auth/login", { username, password });
        setUser(data.user);
      },
      async logout() {
        await postJson<{ logged_out: boolean }>("/auth/logout");
        setUser(null);
      },
      async reloadUser() {
        setUser(await loadCurrentUser());
      },
    }),
    [loading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

export { AuthContext };

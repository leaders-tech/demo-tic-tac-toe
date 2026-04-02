/*
This file builds the main frontend layout, routes, and route guards.
Edit this file when top-level pages, navigation, or auth guard behavior changes.
Copy the route pattern here when you add another top-level page.
*/

import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { LobbyPage } from "../pages/LobbyPage";
import { GamePage } from "../pages/GamePage";
import { AdminPage } from "../pages/AdminPage";

function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200/70 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Layered Tic-Tac-Toe</h1>
            <p className="text-sm text-slate-600">Online 3 by 3 strategy game with stackable pieces.</p>
          </div>
          <nav className="flex items-center gap-3 text-sm font-medium text-slate-700">
            <NavLink className="rounded-full px-3 py-2 hover:bg-slate-100" to="/">
              Home
            </NavLink>
            {user ? (
              <>
                <NavLink className="rounded-full px-3 py-2 hover:bg-slate-100" to="/lobby">
                  Lobby
                </NavLink>
                {user.is_admin && (
                  <NavLink className="rounded-full px-3 py-2 hover:bg-slate-100" to="/admin">
                    Admin
                  </NavLink>
                )}
                <button className="rounded-full bg-slate-900 px-4 py-2 text-white" onClick={() => void logout()}>
                  Logout
                </button>
              </>
            ) : (
              <NavLink className="rounded-full bg-slate-900 px-4 py-2 text-white" to="/login">
                Login
              </NavLink>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="text-slate-600">Loading session...</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="text-slate-600">Loading session...</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.is_admin) {
    return <Navigate to="/lobby" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<Navigate replace to="/lobby" />} />
        <Route
          path="/lobby"
          element={
            <RequireAuth>
              <LobbyPage />
            </RequireAuth>
          }
        />
        <Route
          path="/games/:gameId"
          element={
            <RequireAuth>
              <GamePage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminPage />
            </RequireAdmin>
          }
        />
      </Routes>
    </Layout>
  );
}

export { RequireAdmin, RequireAuth };

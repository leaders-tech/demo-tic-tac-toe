/*
This file shows the public home page for the layered tic-tac-toe game.
Edit this file when the first page text, links, or rules summary changes.
Copy this file as a starting point when you add another public page.
*/

import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <section className="grid gap-6 md:grid-cols-[1.3fr_0.9fr]">
      <div className="rounded-[2rem] bg-slate-900 px-8 py-10 text-white shadow-xl shadow-slate-900/20">
        <p className="mb-3 inline-flex rounded-full bg-white/10 px-3 py-1 text-sm">Online layered tic-tac-toe</p>
        <h2 className="text-4xl font-semibold leading-tight">A live 3 by 3 game where bigger pieces can cover smaller ones.</h2>
        <p className="mt-4 max-w-2xl text-base leading-7 text-slate-200">
          Each player has three small, three medium, and three large pieces. You can place a larger cross or circle on top of any smaller visible piece, and only the top piece counts for three in a row.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link className="rounded-full bg-amber-400 px-5 py-3 font-semibold text-slate-950" to="/login">
            Login and play
          </Link>
        </div>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300">
          This app can use local passwords, and it can also redirect you to Leaders Auth when OIDC login is enabled.
        </p>
      </div>
      <div className="rounded-[2rem] border border-slate-200/80 bg-white/80 p-8 shadow-lg shadow-slate-200/60">
        <h3 className="text-lg font-semibold text-slate-900">How the game works</h3>
        <div className="mt-4 space-y-3 text-sm leading-7 text-slate-700">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Stack rule</p>
            <p>A move is legal on an empty cell or on top of a smaller visible piece.</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Winning rule</p>
            <p>Only the top visible cross or circle in each cell counts for a winning line.</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Online rule</p>
            <p>Logged-in users can create games, join waiting games, or watch active and finished games.</p>
          </div>
        </div>
        <h3 className="mt-6 text-lg font-semibold text-slate-900">Default users in dev</h3>
        <div className="mt-4 space-y-3 text-sm text-slate-700">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Normal user</p>
            <p>Username: user</p>
            <p>Password: user</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Admin user</p>
            <p>Username: admin</p>
            <p>Password: admin</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Viewer user</p>
            <p>Username: viewer</p>
            <p>Password: viewer</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Player user</p>
            <p>Username: nikita</p>
            <p>Password: nikita</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Player user</p>
            <p>Username: elias</p>
            <p>Password: elias</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium">Player user</p>
            <p>Username: alex</p>
            <p>Password: alex</p>
          </div>
        </div>
      </div>
    </section>
  );
}

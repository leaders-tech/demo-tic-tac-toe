# Template PWA

This is a teaching template for school projects. It has a frontend (the part users see in a browser) and a backend (the server that stores data).

**What is inside:**

- **Frontend** — React app with TypeScript, built with Vite, styled with Tailwind CSS.
- **Backend** — Python web server using aiohttp, stores data in a SQLite file.
- **Tests** — automated checks that verify the app works correctly.

---

## Words you will see in this guide

| Word | What it means |
|------|---------------|
| **terminal** | A text window where you type commands. On Mac it is called Terminal, on Windows it is called Command Prompt or PowerShell. |
| **git** | A tool that downloads and tracks code. Every command starts with `git`. |
| **npm** | Node Package Manager — downloads JavaScript libraries that the frontend needs. |
| **uv** | A tool that downloads Python libraries that the backend needs. |
| **make** | A shortcut tool. `make setup` is just a shorter way to run several commands at once. |
| **uv run** | Runs a Python command inside the project's own Python environment. |
| **localhost** | Your own computer. `http://localhost:5173` means "open port 5173 on my own machine". |

---

## Project folders

```
templatePWA/
├── backend/        ← Python server code
│   └── db/         ← Database (SQLite) code
└── frontend/       ← React app code
```

---

## Before you start — check your tools

Do this once on a new machine before cloning anything.

### Check uv (Python package manager)

```bash
uv -V
```

If you get "command not found", install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install a fresh Python:

```bash
uv python install 3.14
```

### Check npm (JavaScript package manager)

```bash
npm -v
```

If you get "command not found", install Node.js via nvm:

```bash
# Install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
# Load nvm without restarting the terminal:
. "$HOME/.nvm/nvm.sh"
# Install Node.js:
nvm install 24
```

---

## First-time setup

Do this once when you first clone the project.

### Step 1 — Download the project

Open a terminal and run:

```bash
git clone https://github.com/leaders-tech/templatePWA.git templatePWA
cd templatePWA
```

`git clone` copies the project to your computer. `cd templatePWA` moves into that folder.

### Step 2 — Install everything

The easiest way (one command does it all):

```bash
make setup
```

That is it. `make setup` installs Python libraries, installs JavaScript libraries, installs browser drivers for tests, and creates the `.env` config files.

<details>
<summary>What does make setup do exactly? (click to expand)</summary>

If you are curious, it runs these steps one by one:

```bash
uv sync --all-groups       # installs Python libraries
cd frontend
npm install                # installs JavaScript libraries
npx playwright install     # installs browsers for end-to-end tests
cp .env.example .env.development.local
cd ..
cp .env.example .env
```

You do not need to run these yourself — `make setup` does it for you.
</details>

---

## Running the app in development

You need **two terminals** open at the same time — one for the backend, one for the frontend.

### Terminal 1 — start the backend (Python server)

```bash
make back
```

The backend will be available at `http://localhost:8000`.

> **With auto-reload:** `make back` already watches for file changes. If you want to run it without auto-reload, use `uv run python -m backend.main`.

### Terminal 2 — start the frontend (React app)

```bash
make front
```

The frontend will be available at `http://localhost:5173`.

Open `http://localhost:5173` in your browser to see the app.

### Default login credentials (development only)

| Username | Password |
|----------|----------|
| user     | user     |
| admin    | admin    |

These accounts exist only in development mode. They are not in production.

---

## How the frontend talks to the backend

The frontend needs to know the backend address. `make front` sets this automatically.

If you start the frontend with `npm run dev` instead, create the file `frontend/.env.development.local` and put this inside:

```
VITE_BACKEND_URL=http://localhost:8000
```

> **Important:** Always use `localhost` for both. Do not mix `localhost` and `127.0.0.1` — the browser may stop sending login cookies if you do.

---

## Adding a new library

### Python library (for the backend)

```bash
uv add package-name
```

For a library only used in development (like a testing tool):

```bash
uv add --dev package-name
```

### JavaScript library (for the frontend)

```bash
cd frontend
npm install package-name
```

For a library only used in development:

```bash
cd frontend
npm install -D package-name
```

> Do not edit the dependency files by hand. Use these commands instead — they also update the lock files automatically.

---

## Running tests

### Backend tests

```bash
uv run pytest
```

### Frontend unit tests

```bash
cd frontend
npm test
```

### End-to-end tests (browser automation)

```bash
cd frontend
npm run test:e2e
```

Playwright opens a real browser, clicks through the app, and checks that everything works.

### Run all tests at once

From the project root:

```bash
make test
```

---

## Formatting code

Formatting makes code look consistent (correct indentation, spacing, etc.).

Python:

```bash
uv run ruff format .
```

Frontend:

```bash
cd frontend
npm run format
```

Or both at once:

```bash
make format
```

---

## Useful make shortcuts

| Command | What it does |
|---------|--------------|
| `make setup` | First-time install of everything |
| `make back` | Start backend with auto-reload |
| `make back-once` | Start backend without auto-reload |
| `make front` | Start frontend dev server |
| `make open` | Open the app in the browser |
| `make format` | Format all code |
| `make test` | Run all tests |

---

## Updating dependencies

Safe update (stays within the same major versions — recommended):

```bash
make deps-update-safe
```

After updating, always run tests to make sure nothing broke:

```bash
make test
make test-e2e-docker
```

---

## Docker (optional, for deployment)

Docker packages the app into containers so it runs the same way everywhere.
You do not need Docker for local development. Use it when you want to test how the app behaves in production.

Quick local test with Docker:

```bash
make back-docker
make front-docker
make open-docker
```

Open in browser:
- Frontend: `http://localhost:8088`
- Backend health check: `http://localhost:8089/health`

Stop and remove containers:

```bash
make stop-docker
make clean-docker
```

---

## Security notes (for learning)

- Passwords are stored as Argon2 hashes — not as plain text.
- Login uses `HttpOnly` cookies so JavaScript cannot read them.
- `SameSite=Lax` cookies protect against most cross-site request attacks.
- In production, the frontend should be served by nginx or Traefik behind a reverse proxy.

---

## Production deployment

This template is designed for [Dokploy](https://dokploy.com/) with Docker Compose.
Set these environment variables in Dokploy instead of editing the `docker-compose.yml` file:

| Variable | What it is |
|----------|------------|
| `DOCKER_COOKIE_SECRET` | Secret key for signing cookies — use a long random string |
| `DOCKER_FRONTEND_ORIGIN` | Public URL of the frontend, e.g. `https://myapp.example.com` |
| `DOCKER_VITE_BACKEND_URL` | Public URL of the backend API |
| `DOCKER_APP_MODE` | `prod` for production, `dev` to enable demo accounts |

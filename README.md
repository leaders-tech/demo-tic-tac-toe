# Demo Tic-Tac-Toe

Online layered tic-tac-toe on a 3 by 3 grid.

## Local setup

You can get the project in one of these two ways.

### Option 1 — open in PyCharm

Create a new project in PyCharm from this Git URL:

```text
https://github.com/leaders-tech/demo-tic-tac-toe.git
```

### Option 2 — clone in the terminal

```bash
git clone https://github.com/leaders-tech/demo-tic-tac-toe.git
cd demo-tic-tac-toe
```

## Install

Run this once after cloning:

```bash
make install
```

This command:
- installs Python packages
- installs frontend packages
- installs Playwright browsers
- creates local `.env` files if they do not exist yet
- creates `.env.docker` from `.env.docker.example` if it does not exist yet

## Run on the same Wi-Fi

Open two terminals.

### Terminal 1

```bash
make back-lan
```

### Terminal 2

```bash
make front-lan
```

Then open the frontend URL printed by `make front-lan`.

Login with:

```text
username: user
password: user
```

`make back-lan` and `make front-lan` use your Wi-Fi IP, so they are useful when you want to open the game from another device on the same network.

## Run on the same computer

If you want to run everything only on your own machine, use:

### Terminal 1

```bash
make back
```

### Terminal 2

```bash
make front
```

Then run:

```bash
make open
```

The exact URLs come from the root `.env` file.

## Default local users

These users exist only in local development:

| Username | Password |
|----------|----------|
| user     | user     |
| admin    | admin    |
| viewer   | viewer   |
| nikita   | nikita   |
| elias    | elias    |
| alex     | alex     |

## Optional local OIDC login

This project can also log in through an external auth service.

If you want local OIDC:
- run the auth service separately
- set the OIDC values in the root `.env`
- run `make back` and `make front`

Use these values:

```text
OIDC_ISSUER_URL=http://localhost:8000
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
```

`OIDC_ISSUER_URL` is the public issuer. It is used for browser redirects and for checking the `iss` claim.

If the backend must reach the auth service on a different internal URL, also set:

```text
OIDC_INTERNAL_BASE_URL=...
```

Use `OIDC_INTERNAL_BASE_URL` only for backend-to-auth-service requests such as discovery, token, JWKS, and userinfo.

For local OIDC with the auth service on `http://localhost:8000`, the backend callback must be:

```text
http://localhost:8001/auth/oidc/callback
```

Example local OIDC `.env`:

```text
APP_MODE=dev
APP_HOST=localhost
APP_PORT=8001
DB_PATH=./dev.sqlite3
COOKIE_SECRET=change-this-secret
FRONTEND_ORIGIN=http://localhost:4175
PUBLIC_BASE_URL=http://localhost:8001
OIDC_ISSUER_URL=http://localhost:8000
OIDC_CLIENT_ID=tic-tac-toe
OIDC_CLIENT_SECRET=your-secret
```

## Docker local run

Docker uses a separate file:

```text
.env.docker
```

This file is used for Docker Compose variable substitution and is also passed into the backend container.

To start Docker locally:

```bash
make back-docker
make front-docker
make open-docker
```

If you want OIDC in Docker, put these values into `.env.docker`:

```text
OIDC_ISSUER_URL=...
OIDC_INTERNAL_BASE_URL=...
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
```

Docker example when the auth service runs on your host machine:

```text
OIDC_ISSUER_URL=http://localhost:8000
OIDC_INTERNAL_BASE_URL=http://host.docker.internal:8000
OIDC_CLIENT_ID=tic-tac-toe
OIDC_CLIENT_SECRET=your-secret
```

`OIDC_ISSUER_URL` must stay the real issuer from the auth service. `OIDC_INTERNAL_BASE_URL` is only the URL that the backend container uses to reach that same auth service.

The example file is:

```text
.env.docker.example
```

## How this project was created from the template

This project was created from this template:

```text
https://github.com/leaders-tech/templatePWA
```

The following prompts were used.

First, in planning mode:

```text
I want to convert this template into a online tic-tac-toe game on 3 by 3 grid.
But with modified rules:
each player has 3 crosses or circles of 3 different sizes. And if a cell is occupied, you can still put a larger cross or circle there.
I want to make it playable online.

What should we think before start planning?
```

Then:

```text
Let's plan it and implement it
```

After that, the answers to the agent questions were given in the UI.

Then:

```text
Implement plan
```

## Useful commands

| Command | What it does |
|---------|--------------|
| `make install` | Install project dependencies and create local env files |
| `make back` | Start the backend on this computer using `.env` |
| `make front` | Start the frontend on this computer using `.env` |
| `make open` | Open the frontend URL from `.env` |
| `make back-lan` | Start the backend for testing on the same Wi-Fi |
| `make front-lan` | Start the frontend for testing on the same Wi-Fi |
| `make back-docker` | Start the backend Docker container using `.env.docker` |
| `make front-docker` | Start the frontend Docker container using `.env.docker` |
| `make open-docker` | Open the Docker frontend URL from `.env.docker` |
| `make test` | Run backend, frontend, and e2e tests |

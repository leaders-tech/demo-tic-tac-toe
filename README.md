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

For local OIDC with the auth service on `http://localhost:8000`, the callback must be:

```text
http://localhost:8001/auth/oidc/callback
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
| `make test` | Run backend, frontend, and e2e tests |

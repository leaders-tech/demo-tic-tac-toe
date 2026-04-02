# Template PWA Agent Notes

- The main user of this template is a school student who does not understand the technology deeply yet.
- Keep the template small and easy to read.
- Prefer the simplest working design over clever abstractions.
- Prefer explicit functions, explicit SQL, and explicit routes.
- Do not add heavy frameworks or hidden magic.
- Keep the current simplified web model unless the user asks for an architecture change:
  - production is same-origin behind nginx or Traefik;
  - dev-only CORS is for localhost splits;
  - browser API calls stay POST-based for this template.
- Keep all user-facing text in simple English.
- When adding backend DB code, place SQL only under `backend/db`.
- When adding frontend pages, keep routing and auth flow direct and beginner-friendly.
- Cover new behavior densely with tests: backend unit tests, frontend unit tests, and Playwright e2e tests where the
  feature crosses the browser boundary.
- For auth, routing, cookies, WebSockets, startup, and other browser-sensitive flows, do not stop at tests. Also verify
  the real running app in a live browser session.
- After frontend, auth, routing, cookie, or WebSocket changes, verify the result in a live browser session, not only
  with tests.
- During that live check, look for browser console errors, failed network requests, cookie problems, and broken
  redirects before calling the task done.
- When local dev servers are already running, prefer checking the real dev app first and use tests as a second line of
  verification.
- Every source file should start with a short plain-English header comment or docstring that explains what the file
  does.
- That file header should also say when the file should be edited, and whether it can be copied as a starting point for
  adding a new table, endpoint, page, test, or similar feature.
- Use module docstrings for Python files.
- Use short top-of-file comments for TS, TSX, JS, CJS, CSS, HTML, env examples, TOML, and the Makefile when the file
  format allows comments.
- If the file format does not support comments cleanly, skip the header instead of breaking the file.
- Keep every file header short. Answer only: what this file does, when to edit it, and when to copy it.
- When a student adds a new feature, prefer the pattern: route -> db/helper file -> page/component -> unit tests ->
  e2e test if the browser flow changed.
- Extend an existing file only when the new code belongs to the same small feature block. Start a sibling file when the
  new code would make the old file feel crowded or mixed.
- Add Python packages with `uv add` for runtime deps and `uv add --dev` for dev-only deps.
- Add frontend packages with `npm install` for runtime deps and `npm install -D` for dev-only deps.
- Do not edit dependency lists by hand unless there is a strong reason and it is explained.

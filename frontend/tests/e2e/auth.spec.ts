/*
This file checks the main browser flows for the online layered tic-tac-toe game.
Edit this file when login, lobby, game routing, reconnect, or rematch browser behavior changes.
Copy a test pattern here when you add another end-to-end browser flow.
*/

import { expect, test, type Browser, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Login with password" }).click();
  await expect(page.getByRole("heading", { name: "Waiting Games" })).toBeVisible();
}

async function openPlayerPage(browser: Browser, username: string, password: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, username, password);
  return page;
}

function currentGameId(page: Page): number {
  const match = /\/games\/(\d+)/.exec(page.url());
  if (!match) {
    throw new Error(`Could not read game id from ${page.url()}`);
  }
  return Number(match[1]);
}

test("players can log in through Leaders Auth and logout again", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("link", { name: "Login with Leaders Auth" }).click();

  await expect(page).toHaveURL(/\/lobby$/);
  await expect(page.getByRole("heading", { name: "Waiting Games" })).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
});

test("players can create, join, and win with a covered top-row move", async ({ browser }) => {
  const xPage = await openPlayerPage(browser, "user", "user");
  const oPage = await openPlayerPage(browser, "admin", "admin");

  await xPage.getByRole("button", { name: "Create new game" }).click();
  await expect(xPage.getByRole("heading", { name: "Waiting for the second player to join." })).toBeVisible();
  const gameId = currentGameId(xPage);

  await oPage.goto("/lobby");
  await oPage.getByRole("button", { name: "Join game" }).click();
  await expect(oPage.getByText("Role: player O")).toBeVisible();
  await expect(xPage.getByText("Role: player X")).toBeVisible();

  await expect(xPage.getByRole("heading", { name: "Turn: X" })).toBeVisible();
  await xPage.getByRole("button", { name: "Cell 1-1" }).click();

  await expect(oPage.getByRole("heading", { name: "Turn: O" })).toBeVisible();
  await oPage.getByRole("button", { name: "Cell 2-1" }).click();

  await expect(xPage.getByRole("heading", { name: "Turn: X" })).toBeVisible();
  await xPage.getByRole("button", { name: "Cell 1-2" }).click();

  await expect(oPage.getByRole("heading", { name: "Turn: O" })).toBeVisible();
  await oPage.getByRole("button", { name: "Medium" }).click();
  await oPage.getByRole("button", { name: "Cell 1-1" }).click();

  await expect(xPage.getByRole("heading", { name: "Turn: X" })).toBeVisible();
  await xPage.getByRole("button", { name: "Cell 3-3" }).click();

  await expect(oPage.getByRole("heading", { name: "Turn: O" })).toBeVisible();
  await oPage.getByRole("button", { name: "Cell 2-2" }).click();

  await expect(xPage.getByRole("heading", { name: "Turn: X" })).toBeVisible();
  await xPage.getByRole("button", { name: "Large" }).click();
  await xPage.getByRole("button", { name: "Cell 1-1" }).click();

  await expect(oPage.getByRole("heading", { name: "Turn: O" })).toBeVisible();
  await oPage.getByRole("button", { name: "Cell 3-2" }).click();

  await expect(xPage.getByRole("heading", { name: "Turn: X" })).toBeVisible();
  await xPage.getByRole("button", { name: "Medium" }).click();
  await xPage.getByRole("button", { name: "Cell 1-3" }).click();

  await expect(xPage.getByRole("heading", { name: "Winner: X" })).toBeVisible();
  await expect(oPage.getByRole("heading", { name: "Winner: X" })).toBeVisible();
  await expect(xPage.getByText("X-small, O-medium, X-large")).toBeVisible();

  expect(currentGameId(oPage)).toBe(gameId);
});

test("spectators receive live updates for active games", async ({ browser }) => {
  const xPage = await openPlayerPage(browser, "user", "user");
  const oPage = await openPlayerPage(browser, "admin", "admin");
  const viewerPage = await openPlayerPage(browser, "viewer", "viewer");

  await xPage.getByRole("button", { name: "Create new game" }).click();
  await oPage.getByRole("button", { name: "Join game" }).click();
  const gameId = currentGameId(xPage);

  await viewerPage.goto("/lobby");
  await viewerPage.getByRole("link", { name: "Watch game" }).first().click();
  await expect(viewerPage.getByText("Role: spectator")).toBeVisible();
  await expect(viewerPage.getByText("Moves played: 0")).toBeVisible();

  await xPage.getByRole("button", { name: "Cell 1-1" }).click();
  await expect(viewerPage.getByText("Moves played: 1")).toBeVisible();

  await oPage.getByRole("button", { name: "Cell 2-2" }).click();
  await expect(viewerPage.getByText("Moves played: 2")).toBeVisible();

  expect(currentGameId(viewerPage)).toBe(gameId);
});

test("players can start a rematch after a finished game", async ({ browser }) => {
  const xPage = await openPlayerPage(browser, "user", "user");
  const oPage = await openPlayerPage(browser, "admin", "admin");

  await xPage.getByRole("button", { name: "Create new game" }).click();
  await oPage.getByRole("button", { name: "Join game" }).click();
  const gameId = currentGameId(xPage);

  await xPage.getByRole("button", { name: "Cell 1-1" }).click();
  await oPage.getByRole("button", { name: "Cell 2-1" }).click();
  await xPage.getByRole("button", { name: "Cell 1-2" }).click();
  await oPage.getByRole("button", { name: "Cell 2-2" }).click();
  await xPage.getByRole("button", { name: "Cell 1-3" }).click();

  await expect(xPage.getByRole("heading", { name: "Winner: X" })).toBeVisible();
  await expect(oPage.getByRole("heading", { name: "Winner: X" })).toBeVisible();

  await xPage.getByRole("button", { name: "Play again" }).click();
  await oPage.getByRole("button", { name: "Play again" }).click();
  await expect(oPage).toHaveURL(/\/games\/\d+$/);
  await expect(xPage.getByRole("link", { name: "Open rematch" })).toBeVisible();
  await xPage.getByRole("link", { name: "Open rematch" }).click();
  await expect(xPage).toHaveURL(/\/games\/\d+$/);
  await expect(currentGameId(xPage)).not.toBe(gameId);
  await expect(xPage.getByRole("heading", { name: "Turn: O" })).toBeVisible();
});

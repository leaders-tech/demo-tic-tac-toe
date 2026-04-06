/*
This file tests the login page form and login-page redirect behavior.
Edit this file when login form behavior or login-page routing changes.
Copy a test pattern here when you add tests for another page with a form.
*/

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";
import { AuthContext } from "../app/auth";
import type { User } from "../shared/types";

const postJson = vi.fn();

vi.mock("../shared/api", () => ({
  getBackendBaseUrl: () => "http://localhost:8000",
  postJson: (...args: unknown[]) => postJson(...args),
}));

const anonymousValue = {
  user: null,
  loading: false,
  login: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
  reloadUser: vi.fn(),
};

const adminUser: User = {
  id: 1,
  username: "admin",
  is_admin: true,
  created_at: "2026-03-06T10:00:00+00:00",
  updated_at: "2026-03-06T10:00:00+00:00",
};

describe("LoginPage", () => {
  beforeEach(() => {
    postJson.mockReset();
    postJson.mockImplementation(() => new Promise(() => {}));
  });

  it("starts with empty username and password fields", () => {
    render(
      <MemoryRouter>
        <AuthContext.Provider value={anonymousValue}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Username")).toHaveValue("");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("submits username and password through auth context", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ ...anonymousValue, login }}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    const usernameInput = screen.getByLabelText("Username");
    const passwordInput = screen.getByLabelText("Password");
    await userEvent.clear(usernameInput);
    await userEvent.type(usernameInput, "admin");
    await userEvent.clear(passwordInput);
    await userEvent.type(passwordInput, "admin");
    await userEvent.click(screen.getByRole("button", { name: "Login with password" }));

    expect(login).toHaveBeenCalledWith("admin", "admin");
  });

  it("shows the Leaders Auth button when OIDC is enabled", async () => {
    postJson.mockResolvedValue({ oidc_enabled: true, oidc_login_url: "/auth/oidc/start" });
    render(
      <MemoryRouter>
        <AuthContext.Provider value={anonymousValue}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("link", { name: "Login with Leaders Auth" })).toHaveAttribute(
      "href",
      "http://localhost:8000/auth/oidc/start",
    );
  });

  it("shows the OIDC callback error from the URL", () => {
    render(
      <MemoryRouter initialEntries={["/login?error=oidc_login_failed"]}>
        <AuthContext.Provider value={anonymousValue}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText("Leaders Auth login failed. Please try again.")).toBeInTheDocument();
  });

  it("redirects logged-in users away from login page", () => {
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ ...anonymousValue, user: adminUser }}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Login")).not.toBeInTheDocument();
  });
});

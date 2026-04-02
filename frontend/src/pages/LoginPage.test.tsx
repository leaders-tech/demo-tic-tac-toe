/*
This file tests the login page form and login-page redirect behavior.
Edit this file when login form behavior or login-page routing changes.
Copy a test pattern here when you add tests for another page with a form.
*/

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";
import { AuthContext } from "../app/auth";
import type { User } from "../shared/types";

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
    await userEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(login).toHaveBeenCalledWith("admin", "admin");
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

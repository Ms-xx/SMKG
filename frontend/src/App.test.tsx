import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { useAuthStore } from "@store/authStore";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("有 token 时调用 fetchUser", () => {
    const fetchUser = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ token: "abc", fetchUser });
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    expect(fetchUser).toHaveBeenCalled();
  });

  it("无 token 时不调用 fetchUser", () => {
    const fetchUser = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ token: null, fetchUser });
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    expect(fetchUser).not.toHaveBeenCalled();
  });
});

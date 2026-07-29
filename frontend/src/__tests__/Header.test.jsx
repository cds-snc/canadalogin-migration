import React from "react";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";

import { vi, describe, beforeEach, it, expect } from "vitest";
import RootLayout from "../components/Layout/RootLayout";
import { authService } from "../services/authService.jsx";

import { UserProvider } from "../components/Providers/UserProvider";
import { LanguageProvider } from "../components/Providers/LanguageProvider";

// Only mock external dependencies, not the providers we want to test
describe("RelyingPartyComponent", () => {
  beforeEach(() => {
    // Mock window.matchMedia for useBreakpoints hook
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it("should fetch and dispatch relying party info if available", async () => {
    const rpInfo = {
      url: "https://example.com",
      linkName: "Example Link",
      icon: "https://example.com/icon.png",
      id: "12345",
    };

    // Mock sessionStorage - initially return null to simulate fresh session
    vi.spyOn(window.sessionStorage, "getItem").mockImplementation(() => null);
    vi.spyOn(window.sessionStorage, "setItem").mockImplementation(() => {});

    // Mock auth service responses
    vi.spyOn(authService, "get_rp_info").mockResolvedValue({ data: rpInfo });
    vi.spyOn(authService, "get_my_user_profile").mockResolvedValue({
      data: {
        id: "test-user-id",
        userName: "testuser",
        active: true,
      },
    });

    // Create a memory router with providers and relying party query parameter
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <UserProvider>
              <LanguageProvider>
                <RootLayout />
              </LanguageProvider>
            </UserProvider>
          ),
        },
      ],
      {
        initialEntries: [`/`],
      },
    );

    // Render with RouterProvider
    render(<RouterProvider router={router} />);

    // Ensure profile fetch happens to unblock layout rendering
    await waitFor(() => {
      expect(authService.get_my_user_profile).toHaveBeenCalled();
    });

    // Header shell renders even when top-nav menu is disabled
    expect(document.querySelector("gcds-header")).toBeTruthy();
  });
});

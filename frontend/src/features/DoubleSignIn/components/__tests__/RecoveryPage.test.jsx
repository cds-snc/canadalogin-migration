import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { appRoutes } from "../../../../routes.jsx";

vi.mock("../../../../components/Providers/UserProvider.tsx", () => ({
  UserProvider: () => {
    throw new Error("Recovery pages must not load the user session");
  },
}));

vi.mock("../../../../components/Layout/Header.jsx", () => ({
  default: ({ langHref, currentLang, showBreadcrumbs }) => (
    <header>
      <a href={langHref}>{currentLang === "fr" ? "English" : "Français"}</a>
      {showBreadcrumbs ? "Session breadcrumbs" : null}
    </header>
  ),
}));

vi.mock("../../../../components/Layout/Footer.jsx", () => ({
  default: () => <footer />,
}));

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
  GcdsText: ({ children }) => <p>{children}</p>,
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
}));

describe("public recovery pages", () => {
  it.each([
    ["en", "missing-rp-context", "Start again from your service"],
    ["en", "session-ended", "Your session has ended"],
    ["en", "service-unavailable", "This service is temporarily unavailable"],
    ["fr", "missing-rp-context", "Recommencez à partir de votre service"],
    ["fr", "session-ended", "Votre session est terminée"],
    ["fr", "service-unavailable", "Ce service est temporairement indisponible"],
  ])(
    "renders %s/%s without authentication",
    async (language, reason, title) => {
      const router = createMemoryRouter(appRoutes, {
        initialEntries: [`/${language}/error/${reason}`],
      });
      render(<RouterProvider router={router} />);

      expect(
        await screen.findByRole("heading", { level: 1, name: title }),
      ).toBeInTheDocument();
      expect(document.title).toContain(title);
      expect(document.documentElement.lang).toBe(language);
      expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
      expect(
        screen.getByRole("link", {
          name: language === "en" ? "Français" : "English",
        }),
      ).toHaveAttribute(
        "href",
        `/${language === "en" ? "fr" : "en"}/error/${reason}`,
      );
      expect(screen.queryByText("Session breadcrumbs")).not.toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(
        /Redis|client.?id|HTTP|exception/i,
      );
    },
  );

  it("uses a safe generic message for an unknown reason", async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/en/error/unrecognized"],
    });
    render(<RouterProvider router={router} />);
    expect(
      await screen.findByRole("heading", {
        name: "This service is temporarily unavailable",
      }),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("unrecognized");
  });
});

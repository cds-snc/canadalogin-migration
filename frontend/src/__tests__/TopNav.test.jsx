import { render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import TopNav from "../components/Layout/TopNav.jsx";
import { useBreakpoints } from "../hooks/useBreakpoints.ts";

vi.mock("../hooks/useBreakpoints.ts", () => ({
  useBreakpoints: vi.fn(),
}));

describe.each([
  ["mobile", { mobile: true, tablet: false }],
  ["tablet", { mobile: false, tablet: true }],
])("TopNav on %s", (_viewport, breakpoints) => {
  it.each([
    ["en", "CanadaLogin"],
    ["fr", "ConnexionCanada"],
  ])("contains the %s navigation item in a list", async (language, label) => {
    useBreakpoints.mockReturnValue(breakpoints);

    render(<TopNav currentLang={language} />);

    // Use the real GCDS component so its generated listitem role is checked.
    await waitFor(() => expect(screen.getByRole("listitem")).toBeTruthy());
    const list = screen.getByRole("list");
    expect(within(list).getByRole("listitem")).toHaveTextContent(label);
  });
});

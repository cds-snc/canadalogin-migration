import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import SkipLink from "../SkipLink.jsx";
import { MIGRATION_END_POINTS } from "../../../../utils/constants.jsx";

vi.mock("@cdssnc/gcds-components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsText: ({ children }) => <div>{children}</div>,
  GcdsDetails: ({ children }) => <div>{children}</div>,
  GcdsInput: ({ children }) => <div>{children}</div>,
  GcdsStepper: ({ children }) => <div>{children}</div>,
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsCheckboxes: ({ children }) => <div>{children}</div>,
  GcdsGrid: ({ children }) => <div>{children}</div>,
  GcdsButton: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
}));

vi.mock("react-router", () => ({
  useParams: () => ({ language: "en" }),
}));

const mockSearchParams = new URLSearchParams();
vi.mock("react-router-dom", () => ({
  useSearchParams: () => [mockSearchParams],
}));

vi.mock("../../../../utils/functions.jsx", () => ({
  getPageContent: (_language, page) => {
    if (page === "SkipLink") {
      return {
        title: "Skip linking",
        text_1: "You can skip.",
        text_2: "Are you sure?",
        btn_1: "Go back",
        btn_2: "Skip",
      };
    }
    return {};
  },
}));

describe("SkipLink", () => {
  it("renders links for login and skip", () => {
    render(<SkipLink />);
    expect(screen.getByText("Skip linking")).toBeInTheDocument();

    const goBack = screen.getByText("Go back");
    const skip = screen.getByText("Skip");

    expect(goBack).toHaveAttribute("href", MIGRATION_END_POINTS.login);
    expect(skip).toHaveAttribute("href", MIGRATION_END_POINTS.login);
  });
});

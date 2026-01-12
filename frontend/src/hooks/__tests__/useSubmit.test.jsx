import { describe, it, expect, vi, beforeEach } from "vitest";

import { callAnalytics, callAuthService } from "../useSubmit.tsx";
import { SUBMIT_END_POINTS, PAGES } from "../../utils/constants.jsx";

vi.mock("../../services/authService.jsx", () => ({
  authService: {
    create: vi.fn(),
    login: vi.fn(),
    otpVerify: vi.fn(),
    otpSend: vi.fn(),
    createCoreProfile: vi.fn(),
  },
}));

vi.mock("../../utils/gatag.jsx", () => ({
  trackEvent: vi.fn(),
}));

import { authService } from "../../services/authService.jsx";
import { trackEvent } from "../../utils/gatag.jsx";

describe("useSubmit helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("callAuthService maps create payload", async () => {
    authService.create.mockResolvedValue({ ok: true });
    const response = await callAuthService(
      { endpoint: SUBMIT_END_POINTS.create },
      { password: "pw" },
      { email: "user@example.com", trxnId: "t-1" },
    );
    expect(authService.create).toHaveBeenCalledWith({
      userName: "user@example.com",
      password: "pw",
      trxnId: "t-1",
    });
    expect(response).toEqual({ ok: true });
  });

  it("callAuthService maps otpVerify payload", async () => {
    authService.otpVerify.mockResolvedValue({ ok: true });
    const response = await callAuthService(
      { endpoint: SUBMIT_END_POINTS.otpVerify, type: "smsotp" },
      { verificationCode: "123456" },
      { email: "user@example.com", trxnId: "t-2" },
    );
    expect(authService.otpVerify).toHaveBeenCalledWith({
      otp: "123456",
      otpType: "smsotp",
      userName: "user@example.com",
      trxnId: "t-2",
    });
    expect(response).toEqual({ ok: true });
  });

  it("callAuthService returns empty object for unknown endpoint", async () => {
    const response = await callAuthService(
      { endpoint: "unknown" },
      {},
      { email: "user@example.com" },
    );
    expect(response).toEqual({});
  });

  it("callAnalytics emits tracking event", async () => {
    await callAnalytics(
      { page: PAGES.password, flow: "flow" },
      "submit_success",
      "Button",
    );
    expect(trackEvent).toHaveBeenCalledWith({
      category: "flow",
      action: "password_submit_success",
      label: "Button",
    });
  });
});

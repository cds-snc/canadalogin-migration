import { describe, it, expect } from "vitest";

import {
  getLegacyIdpOptions,
  getLegacyProviderDisplayName,
  getLegacyProviderType,
  getLocalizedRpName,
  getRpAnalyticsParams,
  replaceRpName,
  replaceProviderName,
} from "../relyingParty.js";

describe("relyingParty utils", () => {
  it("prefers the French RP name when available", () => {
    expect(
      getLocalizedRpName(
        {
          rp_client_name: "CDCP",
          rp_client_name_en: "Canadian Dental Care Plan",
          rp_client_name_fr: "Régime canadien de soins dentaires",
        },
        "fr",
      ),
    ).toBe("Régime canadien de soins dentaires");
  });

  it("falls back to the generic RP name before switching languages", () => {
    expect(
      getLocalizedRpName(
        {
          rp_client_name: "CDCP",
          rp_client_name_en: "Canadian Dental Care Plan",
        },
        "fr",
      ),
    ).toBe("CDCP");
  });

  it("replaces the RP token with the resolved name", () => {
    expect(
      replaceRpName("Compte du {RP_Name}", { rp_client_name: "CDCP" }, "fr"),
    ).toBe("Compte du CDCP");
  });

  it("builds analytics parameters with the English RP name", () => {
    expect(
      getRpAnalyticsParams({
        rp_client_id: "rp-123",
        rp_client_name_en: "Canadian Dental Care Plan",
        rp_client_name_fr: "Régime canadien de soins dentaires",
      }),
    ).toEqual({
      rp_id: "rp-123",
      rp_name: "Canadian Dental Care Plan",
    });
  });

  it("normalizes known legacy provider types", () => {
    expect(getLegacyProviderType({ provider_key: "gckey-sim" })).toBe("gckey");
    expect(getLegacyProviderType({ provider_key: "interac-sim" })).toBe(
      "interac",
    );
    expect(getLegacyProviderType({ provider_key: "cbs-sim" })).toBe("interac");
  });

  it("returns localized provider display names for known providers", () => {
    expect(
      getLegacyProviderDisplayName({ provider_key: "gckey-sim" }, "fr"),
    ).toBe("CléGC");
    expect(
      getLegacyProviderDisplayName({ provider_key: "interac-sim" }, "en"),
    ).toBe("Interac sign-in partner");
  });

  it("falls back to configured display name for unknown providers", () => {
    expect(
      getLegacyProviderDisplayName(
        { provider_key: "gccf-custom", display_name: "GCCF Custom" },
        "en",
      ),
    ).toBe("GCCF Custom");
  });

  it("deduplicates configured provider choices by provider key", () => {
    expect(
      getLegacyIdpOptions({
        legacy_idps: [
          { provider_key: "gckey-sim" },
          { provider_key: "gckey-sim" },
          { provider_key: "interac-sim" },
        ],
      }),
    ).toEqual([{ provider_key: "gckey-sim" }, { provider_key: "interac-sim" }]);
  });

  it("replaces the provider token with the localized provider name", () => {
    expect(
      replaceProviderName(
        "Sign in with {provider_name}",
        { provider_key: "gckey-sim" },
        "en",
      ),
    ).toBe("Sign in with GCKey");
  });
});

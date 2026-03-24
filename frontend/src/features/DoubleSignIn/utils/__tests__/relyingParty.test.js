import { describe, it, expect } from "vitest";

import { getLocalizedRpName, replaceRpName } from "../relyingParty.js";

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
});

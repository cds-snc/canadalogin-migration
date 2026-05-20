const RP_NAME_TOKEN = "{RP_Name}";
const PROVIDER_NAME_TOKEN = "{provider_name}";

const LEGACY_PROVIDER_ALIASES = {
  gckey: ["gckey", "gckey-sim"],
  interac: ["interac", "interac-sim", "cbs", "cbs-sim"],
  sic: ["sic"],
  gccf: ["gccf"],
};

const LEGACY_PROVIDER_NAMES = {
  en: {
    gckey: "GCKey",
    interac: "Interac sign-in partner",
    sic: "GCKey or Interac sign-in partner",
    gccf: "GCCF",
  },
  fr: {
    gckey: "CléGC",
    interac: "partenaire de connexion Interac",
    sic: "CléGC ou partenaire de connexion Interac",
    gccf: "GCCF",
  },
};

function isPresent(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function normalizeProviderValue(value) {
  return isPresent(value) ? value.trim().toLowerCase() : "";
}

export function getLegacyProviderType(provider) {
  const values = [
    provider?.provider_key,
    provider?.client_name,
    provider?.display_name,
  ].map(normalizeProviderValue);

  return (
    Object.entries(LEGACY_PROVIDER_ALIASES).find(([, aliases]) =>
      aliases.some((alias) => values.includes(alias)),
    )?.[0] || ""
  );
}

export function getLegacyProviderDisplayName(provider, language) {
  const providerType = getLegacyProviderType(provider);
  const localizedName = LEGACY_PROVIDER_NAMES[language]?.[providerType];

  if (localizedName) {
    return localizedName;
  }

  return (
    [provider?.display_name, provider?.client_name, provider?.provider_key]
      .find(isPresent)
      ?.trim() || ""
  );
}

export function getLegacyIdpOptions(rpData) {
  if (!Array.isArray(rpData?.legacy_idps)) {
    return [];
  }

  const seenProviderKeys = new Set();

  return rpData.legacy_idps.filter((provider) => {
    const providerKey = normalizeProviderValue(provider?.provider_key);

    if (!providerKey || seenProviderKeys.has(providerKey)) {
      return false;
    }

    seenProviderKeys.add(providerKey);
    return true;
  });
}

export function replaceProviderName(text, provider, language) {
  if (typeof text !== "string") {
    return "";
  }

  return text.replace(
    PROVIDER_NAME_TOKEN,
    getLegacyProviderDisplayName(provider, language),
  );
}

export function getLocalizedRpName(rpData, language) {
  const preferredNames =
    language === "fr"
      ? [
          rpData?.rp_client_name_fr,
          rpData?.rp_client_name,
          rpData?.rp_client_name_en,
        ]
      : [
          rpData?.rp_client_name_en,
          rpData?.rp_client_name,
          rpData?.rp_client_name_fr,
        ];

  return preferredNames.find(isPresent)?.trim() || "";
}

export function replaceRpName(text, rpData, language) {
  if (typeof text !== "string") {
    return "";
  }

  return text.replace(RP_NAME_TOKEN, getLocalizedRpName(rpData, language));
}

export function getRpAnalyticsParams(rpData) {
  return {
    rp_id: rpData?.rp_client_id,
    rp_name: isPresent(rpData?.rp_client_name_en)
      ? rpData.rp_client_name_en.trim()
      : undefined,
  };
}

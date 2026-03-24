const RP_NAME_TOKEN = "{RP_Name}";

function isPresent(value) {
  return typeof value === "string" && value.trim().length > 0;
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

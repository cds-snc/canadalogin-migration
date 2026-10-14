import { apiClient } from "../../../services/apiClient.js";
import { MIGRATION_END_POINTS } from "../../../utils/constants.jsx";
import { handleApiError } from "../../../utils/apiErrorHandler.js";

let migrationStatusRequest = null;

export const updateLinkStateAPI = {
  getRecoveryRPDetails: async (language) => {
    // Configuration only: no IBM profile read or migration update. Failure
    // leaves the recovery instructions visible instead of redirecting again.
    const { data } = await apiClient.get(MIGRATION_END_POINTS.rpcallback, {
      params: { lang: language },
    });
    return data;
  },
  getMigrationStatus: ({ forceFresh = false } = {}) => {
    // Share checks within a visit; a later visit must bypass an older pending read.
    if (forceFresh || !migrationStatusRequest) {
      const request = apiClient
        .get(MIGRATION_END_POINTS.status)
        .then(({ data }) => {
          if (
            typeof data?.rp_client_id !== "string" ||
            !data.rp_client_id.trim() ||
            typeof data?.completed !== "boolean"
          ) {
            throw new Error("The server did not return a migration status.");
          }
          return data;
        })
        .finally(() => {
          if (migrationStatusRequest === request) migrationStatusRequest = null;
        });
      migrationStatusRequest = request;
    }
    // The return guard handles errors without automatically starting login.
    return migrationStatusRequest;
  },
  getRPAuthUrl: async () => {
    try {
      console.log("====== start getRPAuthUrl ======");
      console.log(
        `====== API Endpoint: ${MIGRATION_END_POINTS.rpcallback} ======`,
      );

      const response = await apiClient.get(MIGRATION_END_POINTS.rpcallback);

      var rpData = response.data;

      console.log(`====== rpData : ${rpData} ======`);
      console.log("====== end getRPAuthUrl ======");

      return rpData;
    } catch (error) {
      handleApiError(error);
    }
  },
  skipLinking: async (language) => {
    try {
      const response = await apiClient.post(
        `${MIGRATION_END_POINTS.skip}?lang=${encodeURIComponent(language)}`,
      );
      if (
        typeof response.data?.redirect_url !== "string" ||
        !response.data.redirect_url
      ) {
        throw new Error("The server did not return a redirect URL.");
      }
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};

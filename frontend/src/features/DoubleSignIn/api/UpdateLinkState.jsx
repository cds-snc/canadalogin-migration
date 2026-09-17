import { apiClient } from "../../../services/apiClient.js";
import { MIGRATION_END_POINTS } from "../../../utils/constants.jsx";
import { handleApiError } from "../../../utils/apiErrorHandler.js";

export const updateLinkStateAPI = {
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

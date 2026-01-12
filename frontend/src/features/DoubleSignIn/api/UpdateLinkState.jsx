import axios from "axios";
import { MIGRATION_END_POINTS } from "../../../utils/constants.jsx";
import { handleApiError } from "../../../utils/apiErrorHandler.js";

axios.defaults.withCredentials = true;

export const updateLinkStateAPI = {
  getRPAuthUrl: async () => {
    try {
      console.log("====== start getRPAuthUrl ======");
      console.log(
        `====== API Endpoint: ${MIGRATION_END_POINTS.rpcallback} ======`,
      );

      const response = await axios.get(`${MIGRATION_END_POINTS.rpcallback}`);

      var rpData = response.data;

      console.log(`====== rpData : ${rpData} ======`);
      console.log("====== end getRPAuthUrl ======");

      return rpData;
    } catch (error) {
      handleApiError(error);
    }
  },
};

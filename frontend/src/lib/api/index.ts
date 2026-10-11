export * from "./common";
export * from "./conversations";
export * from "./external-turns";

import { conversationEndpoints } from "./conversations";
import { externalTurnEndpoints } from "./external-turns";

/** Compatibility façade for existing UI consumers. */
export const conversationsApi = { ...conversationEndpoints, ...externalTurnEndpoints };

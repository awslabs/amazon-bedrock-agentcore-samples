import { Mastra } from "@mastra/core/mastra";
import { utilityAgent } from "./agents/utility-agent.js";

export const mastra = new Mastra({
  agents: { utilityAgent },
});
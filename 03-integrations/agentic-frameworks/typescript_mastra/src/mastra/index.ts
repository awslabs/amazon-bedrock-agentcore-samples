import { Mastra } from "@mastra/core/mastra";
import { utilityAgent } from "./agents/utility-agent";

export const mastra = new Mastra({
  agents: { utilityAgent },
});
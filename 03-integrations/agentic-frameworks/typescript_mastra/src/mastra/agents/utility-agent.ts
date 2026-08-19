import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { z } from "zod";

/**
 * Tool: Get Current Time
 * Returns the current time in a specified timezone
 */
export const getCurrentTimeTool = createTool({
  id: "get-current-time",
  description: "Get the current time in a specified timezone. Use this when the user asks for the current time.",
  inputSchema: z.object({
    timezone: z.string().describe("The timezone to get the time for (e.g., 'America/New_York', 'UTC', 'Asia/Tokyo')").default("UTC"),
  }),
  outputSchema: z.object({
    currentTime: z.string(),
    timezone: z.string(),
    timestamp: z.number(),
  }),
  execute: async ({ context }: { context: { timezone: string } }) => {
    const { timezone } = context;

    const now = new Date();
    const timestamp = now.getTime();

    // Format time for the specified timezone
    const currentTime = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      dateStyle: 'full',
      timeStyle: 'long',
    }).format(now);

    return {
      currentTime,
      timezone,
      timestamp,
    };
  },
});

/**
 * Tool: Calculate
 * Performs basic arithmetic operations
 */
export const calculateTool = createTool({
  id: "calculate",
  description: "Perform basic arithmetic calculations. Supports addition, subtraction, multiplication, and division.",
  inputSchema: z.object({
    operation: z.enum(["add", "subtract", "multiply", "divide"]).describe("The arithmetic operation to perform"),
    a: z.number().describe("The first number"),
    b: z.number().describe("The second number"),
  }),
  outputSchema: z.object({
    result: z.number(),
    operation: z.string(),
    expression: z.string(),
  }),
  execute: async ({ context }: { context: { operation: "add" | "subtract" | "multiply" | "divide", a: number, b: number } }) => {
    const { operation, a, b } = context;

    let result: number = 0;
    let expression: string = "";

    switch (operation) {
      case "add":
        result = a + b;
        expression = `${a} + ${b} = ${result}`;
        break;
      case "subtract":
        result = a - b;
        expression = `${a} - ${b} = ${result}`;
        break;
      case "multiply":
        result = a * b;
        expression = `${a} × ${b} = ${result}`;
        break;
      case "divide":
        if (b === 0) {
          throw new Error("Cannot divide by zero");
        }
        result = a / b;
        expression = `${a} ÷ ${b} = ${result}`;
        break;
    }

    return {
      result,
      operation,
      expression,
    };
  },
});

/**
 * Tool: Generate Random Number
 * Generates a random number within a specified range
 */
export const generateRandomNumberTool = createTool({
  id: "generate-random-number",
  description: "Generate a random number within a specified range (inclusive).",
  inputSchema: z.object({
    min: z.number().describe("The minimum value (inclusive)").default(1),
    max: z.number().describe("The maximum value (inclusive)").default(100),
  }),
  outputSchema: z.object({
    randomNumber: z.number(),
    min: z.number(),
    max: z.number(),
  }),
  execute: async ({ context }: { context: { min: number, max: number } }) => {
    const { min, max } = context;

    if (min > max) {
      throw new Error("Minimum value cannot be greater than maximum value");
    }

    const randomNumber = Math.floor(Math.random() * (max - min + 1)) + min;

    return {
      randomNumber,
      min,
      max,
    };
  },
});

/**
 * Utility Agent
 * A helpful assistant with access to various utility tools
 */
export const utilityAgent = new Agent({
  name: "utilityAgent",
  instructions: `You are a helpful assistant with access to several utility tools.

Your capabilities include:
- Getting the current time in any timezone
- Performing basic arithmetic calculations (addition, subtraction, multiplication, division)
- Generating random numbers within a specified range

When a user asks you to perform any of these tasks, use the appropriate tool. Be friendly, clear, and accurate in your responses.`,
  model: "openai/gpt-4o-mini",
  tools: {
    getCurrentTimeTool,
    calculateTool,
    generateRandomNumberTool,
  },
});

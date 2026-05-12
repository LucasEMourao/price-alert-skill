import pino from "pino";
import type { GatewayConfig } from "./config.js";

export function createLogger(config: GatewayConfig) {
  return pino({
    level: config.logLevel,
  });
}

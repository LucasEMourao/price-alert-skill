import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const gatewayRoot = path.resolve(currentDir, "..");
const repoRoot = path.resolve(gatewayRoot, "..");

function parsePort(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export type GatewayConfig = {
  host: string;
  port: number;
  authDir: string;
  logLevel: string;
};

export function loadConfig(): GatewayConfig {
  return {
    host: process.env.BAILEYS_HOST || "127.0.0.1",
    port: parsePort(process.env.BAILEYS_PORT, 3015),
    authDir:
      process.env.BAILEYS_AUTH_DIR ||
      path.join(repoRoot, ".agents", "skills", "price-alert-skill", "data", "baileys_auth"),
    logLevel: process.env.BAILEYS_LOG_LEVEL || "info",
  };
}

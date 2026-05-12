import { createServer } from "node:http";
import { loadConfig } from "./config.js";
import { createLogger } from "./logger.js";
import { createApp } from "./server.js";
import { BaileysGateway } from "./whatsapp.js";

const config = loadConfig();
const logger = createLogger(config);
const gateway = new BaileysGateway(config, logger);
const app = createApp(config, gateway, logger);
const server = createServer(app);

async function shutdown(signal: string) {
  logger.info({ signal }, "Stopping WhatsApp gateway");
  server.close(() => {
    logger.info("HTTP server stopped");
  });
  await gateway.stop();
  process.exit(0);
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));

await gateway.start();

server.listen(config.port, config.host, () => {
  logger.info(
    {
      host: config.host,
      port: config.port,
      authDir: config.authDir,
    },
    "WhatsApp gateway listening",
  );
});

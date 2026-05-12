import express from "express";
import type { Logger } from "pino";
import type { GatewayConfig } from "./config.js";
import type { BaileysGateway } from "./whatsapp.js";

export function createApp(config: GatewayConfig, gateway: BaileysGateway, logger: Logger) {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "1mb" }));

  app.get("/health", (_req, res) => {
    res.json({
      ok: true,
      service: "price-alert-whatsapp-gateway",
      backend: "baileys",
      host: config.host,
      port: config.port,
      whatsapp: gateway.status(),
    });
  });

  app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    logger.error({ error }, "Unhandled gateway request error");
    res.status(500).json({ success: false, reason: "internal_error" });
  });

  return app;
}

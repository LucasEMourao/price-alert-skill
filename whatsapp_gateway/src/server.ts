import express from "express";
import type { Logger } from "pino";
import type { GatewayConfig } from "./config.js";
import type { BaileysGateway } from "./whatsapp.js";

type SendTextBody = {
  group_jid?: string;
  jid?: string;
  message?: string;
};

type SendImageBody = {
  group_jid?: string;
  jid?: string;
  image_url?: string;
  caption?: string;
};

function parseBooleanQuery(value: unknown): boolean {
  return value === "1" || value === "true" || value === "yes";
}

function resolveJid(body: { group_jid?: string; jid?: string }): string {
  return String(body.group_jid || body.jid || "").trim();
}

function badRequest(res: express.Response, reason: string) {
  res.status(400).json({ success: false, reason });
}

function handleGatewayError(
  error: unknown,
  gateway: BaileysGateway,
  res: express.Response,
  next: express.NextFunction,
) {
  if (error instanceof Error && error.message === "baileys_not_connected") {
    res.status(409).json({
      success: false,
      reason: "baileys_not_connected",
      whatsapp: gateway.status(),
    });
    return;
  }
  next(error);
}

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

  app.get("/groups", async (req, res, next) => {
    try {
      const groups = await gateway.listGroups(parseBooleanQuery(req.query.include_participants));
      res.json({ success: true, groups });
    } catch (error) {
      handleGatewayError(error, gateway, res, next);
    }
  });

  app.post("/send-text", async (req, res, next) => {
    const body = req.body as SendTextBody;
    const jid = resolveJid(body);
    const message = String(body.message || "").trim();
    if (!jid) {
      badRequest(res, "missing_group_jid");
      return;
    }
    if (!message) {
      badRequest(res, "missing_message");
      return;
    }

    try {
      res.json(await gateway.sendText(jid, message));
    } catch (error) {
      handleGatewayError(error, gateway, res, next);
    }
  });

  app.post("/send-image", async (req, res, next) => {
    const body = req.body as SendImageBody;
    const jid = resolveJid(body);
    const imageUrl = String(body.image_url || "").trim();
    const caption = String(body.caption || "");
    if (!jid) {
      badRequest(res, "missing_group_jid");
      return;
    }
    if (!imageUrl) {
      badRequest(res, "missing_image_url");
      return;
    }

    try {
      res.json(await gateway.sendImage(jid, imageUrl, caption));
    } catch (error) {
      handleGatewayError(error, gateway, res, next);
    }
  });

  app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    logger.error({ error }, "Unhandled gateway request error");
    res.status(500).json({ success: false, reason: "internal_error" });
  });

  return app;
}

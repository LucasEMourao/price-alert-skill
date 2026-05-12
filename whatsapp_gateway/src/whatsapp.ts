import fs from "node:fs/promises";
import QRCode from "qrcode";
import makeWASocket, {
  Browsers,
  DisconnectReason,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
  type ConnectionState,
  type GroupMetadata,
  type WASocket,
} from "baileys";
import type { Logger } from "pino";
import type { GatewayConfig } from "./config.js";

type PublicStatus = {
  connected: boolean;
  connection: ConnectionState["connection"] | "idle";
  authDir: string;
  startedAt: string;
  lastConnectedAt: string | null;
  lastDisconnectAt: string | null;
  lastDisconnectReason: string | null;
  hasQr: boolean;
};

export type GroupSummary = {
  jid: string;
  subject: string;
  owner: string | null;
  participantCount: number;
  participants?: Array<{ jid: string; admin: string | null }>;
};

export class BaileysGateway {
  private socket: WASocket | null = null;
  private connecting = false;
  private connection: PublicStatus["connection"] = "idle";
  private lastQr: string | null = null;
  private lastConnectedAt: string | null = null;
  private lastDisconnectAt: string | null = null;
  private lastDisconnectReason: string | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private readonly startedAt = new Date().toISOString();

  constructor(
    private readonly config: GatewayConfig,
    private readonly logger: Logger,
  ) {}

  async start(): Promise<void> {
    await fs.mkdir(this.config.authDir, { recursive: true });
    await this.connect();
  }

  status(): PublicStatus {
    return {
      connected: this.connection === "open",
      connection: this.connection,
      authDir: this.config.authDir,
      startedAt: this.startedAt,
      lastConnectedAt: this.lastConnectedAt,
      lastDisconnectAt: this.lastDisconnectAt,
      lastDisconnectReason: this.lastDisconnectReason,
      hasQr: Boolean(this.lastQr),
    };
  }

  async listGroups(includeParticipants = false): Promise<GroupSummary[]> {
    const socket = this.requireConnectedSocket();
    const groups = await socket.groupFetchAllParticipating();
    return Object.values(groups)
      .map((metadata) => this.toGroupSummary(metadata, includeParticipants))
      .sort((left, right) => left.subject.localeCompare(right.subject, "pt-BR"));
  }

  async stop(): Promise<void> {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.end(undefined);
    this.socket = null;
    this.connection = "close";
  }

  private requireConnectedSocket(): WASocket {
    if (!this.socket || this.connection !== "open") {
      throw new Error("baileys_not_connected");
    }
    return this.socket;
  }

  private toGroupSummary(metadata: GroupMetadata, includeParticipants: boolean): GroupSummary {
    const participants = metadata.participants || [];
    const summary: GroupSummary = {
      jid: metadata.id,
      subject: metadata.subject || "",
      owner: metadata.owner || null,
      participantCount: participants.length,
    };

    if (includeParticipants) {
      summary.participants = participants.map((participant) => ({
        jid: participant.id,
        admin: participant.admin || null,
      }));
    }

    return summary;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect().catch((error: unknown) => {
        this.logger.error({ error }, "Baileys reconnect failed");
        this.scheduleReconnect();
      });
    }, 5000);
  }

  private async connect(): Promise<void> {
    if (this.connecting) {
      return;
    }
    this.connecting = true;
    try {
      const { state, saveCreds } = await useMultiFileAuthState(this.config.authDir);
      const socket = makeWASocket({
        auth: {
          creds: state.creds,
          keys: makeCacheableSignalKeyStore(state.keys, this.logger),
        },
        browser: Browsers.macOS("Desktop"),
        logger: this.logger,
        markOnlineOnConnect: false,
        syncFullHistory: false,
        getMessage: async () => undefined,
      });

      this.socket = socket;
      socket.ev.on("creds.update", saveCreds);
      socket.ev.on("connection.update", (update) => {
        void this.handleConnectionUpdate(update);
      });
    } finally {
      this.connecting = false;
    }
  }

  private async handleConnectionUpdate(update: Partial<ConnectionState>): Promise<void> {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      this.lastQr = qr;
      this.logger.info("Baileys QR received. Scan it as a linked WhatsApp device.");
      const qrText = await QRCode.toString(qr, { type: "terminal", small: true });
      // QR content is intentionally printed to stdout for first-login operations.
      console.log(qrText);
    }

    if (connection) {
      this.connection = connection;
      this.logger.info({ connection }, "Baileys connection update");
    }

    if (connection === "open") {
      this.lastQr = null;
      this.lastConnectedAt = new Date().toISOString();
      this.lastDisconnectReason = null;
      return;
    }

    if (connection !== "close") {
      return;
    }

    this.lastDisconnectAt = new Date().toISOString();
    const statusCode = (lastDisconnect?.error as any)?.output?.statusCode;
    const reasonName =
      Object.entries(DisconnectReason).find(([, value]) => value === statusCode)?.[0] ||
      String(statusCode || "unknown");
    this.lastDisconnectReason = reasonName;
    this.logger.warn({ statusCode, reasonName }, "Baileys connection closed");

    if (statusCode === DisconnectReason.loggedOut) {
      this.logger.error("Baileys session logged out. Delete the auth dir and scan again.");
      return;
    }

    this.scheduleReconnect();
  }
}

require("dotenv").config();

const express = require("express");
const cors = require("cors");
const QRCode = require("qrcode");
const fs = require("fs");
const path = require("path");
const whatsapp = require("wa-multi-session");

const app = express();
const port = Number(process.env.WA_GATEWAY_PORT || 3001);
const host = process.env.WA_GATEWAY_HOST || "127.0.0.1";
const apiKey = process.env.WA_GATEWAY_API_KEY || "";
const defaultSession = sanitizeSession(process.env.WA_DEFAULT_SESSION || "sikap-pu-main");
const sessionState = new Map();

app.use(cors({ origin: true, credentials: false }));
app.use(express.json({ limit: "1mb" }));

if (typeof whatsapp.setCredentialsDir === "function") {
  whatsapp.setCredentialsDir("wa_credentials");
}
if (typeof whatsapp.loadSessionsFromStorage === "function") {
  try {
    whatsapp.loadSessionsFromStorage();
  } catch (error) {
    console.warn("Gagal memuat session tersimpan:", error.message);
  }
}

if (typeof whatsapp.onQRUpdated === "function") {
  whatsapp.onQRUpdated(({ sessionId, qr }) => updateQr(sessionId, qr));
}

if (typeof whatsapp.onConnected === "function") {
  whatsapp.onConnected((sessionId) => markConnected(sessionId));
}

if (typeof whatsapp.onDisconnected === "function") {
  whatsapp.onDisconnected((sessionId) => markDisconnected(sessionId));
}

app.use((request, response, next) => {
  if (request.path === "/health") return next();
  if (!apiKey) return next();
  const provided = request.get("x-api-key") || "";
  if (provided !== apiKey) {
    return response.status(401).json({ ok: false, error: "API key tidak valid." });
  }
  next();
});

app.get("/health", (request, response) => {
  response.json({ ok: true, service: "Wa-Gateway", defaultSession });
});

app.get("/sessions/:sessionId/status", async (request, response) => {
  const sessionId = sanitizeSession(request.params.sessionId);
  response.json({ ok: true, ...await buildStatus(sessionId) });
});

app.post("/sessions/:sessionId/start", async (request, response) => {
  const sessionId = sanitizeSession(request.params.sessionId);
  const state = ensureState(sessionId);
  state.status = "connecting";
  state.message = "Menyiapkan barcode";
  state.updatedAt = new Date().toISOString();
  try {
    await whatsapp.startSession(sessionId, {
      printQR: false,
      onQRUpdated: (qr) => updateQr(sessionId, qr),
      onConnected: () => markConnected(sessionId),
      onDisconnected: () => markDisconnected(sessionId),
      onConnecting: () => markConnecting(sessionId),
    });
    response.json({ ok: true, ...await buildStatus(sessionId) });
  } catch (error) {
    if (String(error.message || "").includes("already exist")) {
      return response.json({ ok: true, ...await buildStatus(sessionId) });
    }
    state.status = state.status === "active" ? "active" : "need_login";
    state.message = error.message || "Gagal membuka session";
    state.updatedAt = new Date().toISOString();
    response.status(500).json({ ok: false, ...await buildStatus(sessionId), error: state.message });
  }
});

app.post("/sessions/:sessionId/logout", async (request, response) => {
  const sessionId = sanitizeSession(request.params.sessionId);
  try {
    if (typeof whatsapp.deleteSession === "function") {
      await whatsapp.deleteSession(sessionId);
    } else if (typeof whatsapp.logoutSession === "function") {
      await whatsapp.logoutSession(sessionId);
    }
  } catch (error) {
    console.warn("Gagal logout session:", error.message);
  }
  removeCredential(sessionId);
  const state = ensureState(sessionId);
  state.status = "need_login";
  state.message = "Perlu login ulang";
  state.qr = null;
  state.qrDataUrl = null;
  state.qrGenerated = false;
  state.updatedAt = new Date().toISOString();
  response.json({ ok: true, ...await buildStatus(sessionId) });
});

app.post("/sessions/:sessionId/test-message", async (request, response) => {
  const sessionId = sanitizeSession(request.params.sessionId);
  const session = getSession(sessionId);
  const state = ensureState(sessionId);
  if (!session || state.status !== "active") {
    return response.status(409).json({
      ok: false,
      ...await buildStatus(sessionId),
      error: "Session WhatsApp belum aktif. Scan barcode terlebih dahulu.",
    });
  }
  const accountNumber = getSessionPhoneNumber(session);
  if (!accountNumber) {
    return response.status(409).json({
      ok: false,
      ...await buildStatus(sessionId),
      error: "Nomor akun WhatsApp pada session belum terbaca.",
    });
  }
  const text = [
    "Tes pesan SIKAP-PU berhasil.",
    "",
    `Session: ${sessionId}`,
    `Waktu: ${new Date().toLocaleString("id-ID", { timeZone: "Asia/Makassar" })}`,
  ].join("\n");
  try {
    await whatsapp.sendTextMessage({ sessionId, to: accountNumber, text });
    response.json({
      ok: true,
      ...await buildStatus(sessionId),
      target: accountNumber,
      message: `Pesan tes terkirim ke akun WhatsApp ${maskPhone(accountNumber)}.`,
    });
  } catch (error) {
    response.status(500).json({
      ok: false,
      ...await buildStatus(sessionId),
      target: accountNumber,
      error: error.message || "Gagal mengirim pesan tes.",
    });
  }
});

app.post("/messages/send-text", async (request, response) => {
  const sessionId = sanitizeSession(request.body.sessionId || defaultSession);
  const to = String(request.body.to || "").trim();
  const text = String(request.body.text || "").trim();
  if (!to || !text) {
    return response.status(400).json({ ok: false, error: "Nomor tujuan dan teks wajib diisi." });
  }
  try {
    const result = await whatsapp.sendTextMessage({ sessionId, to, text });
    response.json({ ok: true, result });
  } catch (error) {
    response.status(500).json({ ok: false, error: error.message || "Gagal mengirim pesan." });
  }
});

app.listen(port, host, () => {
  console.log(`Wa-Gateway berjalan di http://${host}:${port}`);
  console.log(`Session bawaan: ${defaultSession}`);
});

function sanitizeSession(value) {
  const cleaned = String(value || defaultSession).replace(/[^a-zA-Z0-9_-]/g, "");
  return cleaned || "sikap-pu-main";
}

function ensureState(sessionId) {
  if (!sessionState.has(sessionId)) {
    sessionState.set(sessionId, {
      sessionId,
      status: "need_login",
      message: "Perlu login ulang",
      qr: null,
      qrDataUrl: null,
      updatedAt: null,
      connectedAt: null,
      qrGenerated: false,
    });
  }
  return sessionState.get(sessionId);
}

async function updateQr(sessionId, qr) {
  const state = ensureState(sessionId);
  state.status = "need_login";
  state.message = "Silakan scan barcode WhatsApp";
  state.qr = qr;
  state.qrDataUrl = await QRCode.toDataURL(qr, { margin: 1, width: 320 });
  state.qrGenerated = true;
  state.updatedAt = new Date().toISOString();
}

function markConnecting(sessionId) {
  const state = ensureState(sessionId);
  state.status = "connecting";
  state.message = "Menyiapkan barcode";
  state.updatedAt = new Date().toISOString();
}

function markConnected(sessionId) {
  const state = ensureState(sessionId);
  state.status = "active";
  state.message = "Masih aktif";
  state.qr = null;
  state.qrDataUrl = null;
  state.qrGenerated = false;
  state.connectedAt = new Date().toISOString();
  state.updatedAt = state.connectedAt;
}

function markDisconnected(sessionId) {
  const state = ensureState(sessionId);
  state.status = "need_login";
  state.message = state.qrGenerated
    ? "Perlu login ulang"
    : "Barcode belum bisa dibuat. Periksa koneksi internet/firewall ke WhatsApp Web, lalu coba lagi.";
  state.updatedAt = new Date().toISOString();
}

async function buildStatus(sessionId) {
  const state = ensureState(sessionId);
  const session = getSession(sessionId);
  if (session && state.status === "need_login" && !state.qrDataUrl) {
    state.status = "active";
    state.message = "Masih aktif";
  }
  return {
    sessionId,
    status: state.status,
    connected: state.status === "active",
    message: state.message,
    qrDataUrl: state.qrDataUrl,
    updatedAt: state.updatedAt,
    connectedAt: state.connectedAt,
  };
}

function getSession(sessionId) {
  try {
    if (typeof whatsapp.getSession === "function") return whatsapp.getSession(sessionId);
  } catch (error) {
    return null;
  }
  return null;
}

function removeCredential(sessionId) {
  const credentialPath = path.resolve("wa_credentials", `${sessionId}_credentials`);
  if (credentialPath.includes(path.resolve("wa_credentials"))) {
    fs.rmSync(credentialPath, { recursive: true, force: true });
  }
}

function getSessionPhoneNumber(session) {
  const rawId = session && session.user && session.user.id ? String(session.user.id) : "";
  const jidUser = rawId.split("@")[0].split(":")[0];
  const digits = jidUser.replace(/\D/g, "");
  return digits || "";
}

function maskPhone(number) {
  if (!number || number.length <= 6) return number || "-";
  return `${number.slice(0, 4)}****${number.slice(-3)}`;
}

// Salva l'ultimo config caricato per confronto
let lastSettingsConfig = null;
/**
 * ShibaClaw WebUI — Client Application
 * Socket.IO + Markdown rendering + interactive chat
 */


// ── State ────────────────────────────────────────────────────
const DEFAULT_AVATAR = "/static/shibaclaw_logo.png";

const state = {
    socket: null,
    sessionId: null,
    profileId: "default",
    profileAvatar: DEFAULT_AVATAR,
    _initialConnectDone: false,
    processing: false,
    messageCount: 0,
    queueCount: 0,
    gatewayUp: false,
    gatewayKnown: false,     // Whether health state has been confirmed via API
    gatewayUnreachableCount: 0,  // Consecutive unreachable attempts
    gatewayProviderReady: true,
    agentConfigured: false,
    healthTimer: null,
    historyTimer: null,
    processGroups: {},   // msgId → { el, startTime, stepCount, collapsed }
    authRequired: false,
    stagedFiles: [],     // { name, url, type, stagedAt }
    currentFsPath: ".",  // current path for file explorer
};

let clockTimer = null;


// ── DOM References ────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const chatHistory = $("chat-history");
const chatInput = $("chat-input");
const btnSend = $("btn-send");
const welcomeScreen = $("welcome-screen");
const thinkingIndicator = $("thinking-indicator");
const thinkingText = $("thinking-text");
const statusDot = $("status-dot");
const statusText = $("status-text");
const sessionIdEl = $("session-id");



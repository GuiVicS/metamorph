/**
 * Metamorph Service Worker - Extension Runtime
 *
 * The brain of the extension. Loads fingerprints, builds adapters,
 * executes capabilities, manages events, and communicates with backend.
 */

import { FingerprintStore } from './fingerprint-store.js';
import { AdapterEngine } from './adapter-engine.js';
import { BindingExecutor } from './binding-executor.js';
import { Normalizer } from './normalizer.js';
import { EventBus } from './event-bus.js';
import { HealthMonitor } from './health.js';
import { Transport } from './transport.js';

// ──────────────────────────────────────────────────────────────
// STATE
// ──────────────────────────────────────────────────────────────
const fingerprintStore = new FingerprintStore();
const adapterEngine = new AdapterEngine();
const bindingExecutor = new BindingExecutor();
const normalizer = new Normalizer();
const eventBus = new EventBus();
const healthMonitor = new HealthMonitor();
const transport = new Transport();

let currentFingerprint = null;
let currentAdapter = null;
let installId = null;
let backendUrl = null;

// ──────────────────────────────────────────────────────────────
// INITIALIZATION
// ──────────────────────────────────────────────────────────────
async function initialize() {
  // Get or create install ID
  installId = await getInstallId();

  // Register with backend
  const registered = await transport.register(installId);
  backendUrl = registered.backendWsUrl;

  // Connect WebSocket
  await transport.connect(backendUrl, installId, handleBackendMessage);

  // Load fingerprints from IndexedDB
  await fingerprintStore.init();

  // Load active fingerprints for current tabs
  await syncFingerprints();

  // Start health checks
  healthMonitor.start();

  // Set up alarms for periodic tasks
  chrome.alarms.create('healthCheck', { periodInMinutes: 60 });
  chrome.alarms.create('telemetryFlush', { periodInMinutes: 5 });

  console.log('[Metamorph Worker] Initialized');
}

// ──────────────────────────────────────────────────────────────
// BACKEND MESSAGE HANDLING
// ──────────────────────────────────────────────────────────────
async function handleBackendMessage(message) {
  switch (message.type) {
    case 'welcome':
      console.log('[Metamorph] Backend welcome:', message.instanceId);
      break;
    case 'fingerprint.update':
      await applyFingerprint(message.platform, message.version, message.data);
      break;
    case 'fingerprint.rollback':
      await rollbackFingerprint(message.platform, message.toVersion);
      break;
    case 'probe.request':
      await runProbes(message.fingerprintId, message.probeIds);
      break;
    case 'ping':
      // Keep alive
      break;
  }
}

// ──────────────────────────────────────────────────────────────
// FINGERPRINT MANAGEMENT
// ──────────────────────────────────────────────────────────────
async function syncFingerprints() {
  const fingerprints = await fingerprintStore.getAll();
  for (const [platform, fp] of Object.entries(fingerprints)) {
    if (fp.status === 'active') {
      await applyFingerprint(platform, fp.version, fp.data);
    }
  }
}

async function applyFingerprint(platform, version, fingerprintData) {
  console.log('[Metamorph] Applying fingerprint:', platform, version);

  try {
    // Validate fingerprint
    validateFingerprint(fingerprintData);

    // Build adapter
    const adapter = await adapterEngine.build(fingerprintData);
    currentAdapter = adapter;
    currentFingerprint = fingerprintData;

    // Notify content scripts
    broadcastToContentScripts({ type: 'fingerprintUpdate', fingerprint: fingerprintData });

    // Run non-write probes
    await healthMonitor.runProbes(fingerprintData, { onlyRead: true });

    // Store as active
    await fingerprintStore.setActive(platform, fingerprintData);
  } catch (err) {
    console.error('[Metamorph] Fingerprint apply failed:', err);
    // Rollback to previous
    const prev = await fingerprintStore.getPrevious(platform);
    if (prev) await applyFingerprint(platform, prev.version, prev.data);
    throw err;
  }
}

async function rollbackFingerprint(platform, toVersion) {
  const prev = await fingerprintStore.getVersion(platform, toVersion);
  if (prev) {
    await applyFingerprint(platform, prev.version, prev.data);
  }
}

function validateFingerprint(fp) {
  // Schema validation (simplified)
  if (!fp.schemaVersion) throw new Error('Missing schemaVersion');
  if (!fp.runtime?.discovery) throw new Error('Missing runtime.discovery');
  if (!fp.handles) throw new Error('Missing handles');
  if (!fp.readyCheck) throw new Error('Missing readyCheck');

  // Check for forbidden path segments
  const checkPaths = (obj, path = []) => {
    if (!obj || typeof obj !== 'object') return;
    for (const [key, value] of Object.entries(obj)) {
      if (['__proto__', 'constructor', 'prototype'].includes(key)) {
        throw new Error(`Forbidden path segment: ${key}`);
      }
      if (Array.isArray(value) && value.every(v => typeof v === 'string')) {
        // Could be a path array
      }
      checkPaths(value, [...path, key]);
    }
  };
  checkPaths(fp);
}

// ──────────────────────────────────────────────────────────────
// CAPABILITY EXECUTION (called by popup/content scripts)
// ──────────────────────────────────────────────────────────────
async function executeCapability(capability, args) {
  if (!currentAdapter) throw new Error('No active fingerprint');
  if (!currentAdapter.supports(capability)) {
    throw new Error(`Unsupported capability: ${capability}`);
  }

  const startTime = Date.now();
  try {
    const result = await currentAdapter[capability](args);
    const normalized = normalizer.normalize(capability, result, currentFingerprint);

    // Telemetry
    await telemetry('ok', capability, Date.now() - startTime);

    return normalized;
  } catch (err) {
    await telemetry('error', capability, Date.now() - startTime, err.message);
    throw err;
  }
}

// ──────────────────────────────────────────────────────────────
// CONTENT SCRIPT COMMUNICATION
// ──────────────────────────────────────────────────────────────
const contentPorts = new Map();

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== 'content-script') return;

  const tabId = port.sender.tab?.id;
  contentPorts.set(tabId, port);

  port.onMessage.addListener(async (msg) => {
    try {
      let result;
      switch (msg.type) {
        case 'invoke':
          result = await executeCapability(msg.capability, msg.args);
          port.postMessage({ type: 'response', requestId: msg.requestId, result });
          break;
        case 'subscribe':
          // Set up event subscription
          const unsubscribe = currentAdapter.on(msg.capability, (data) => {
            port.postMessage({ type: 'event', capability: msg.capability, data });
          });
          port.postMessage({ type: 'response', requestId: msg.requestId, result: { subscribed: true } });
          // Store unsubscribe for cleanup
          port.onDisconnect.addListener(() => unsubscribe?.());
          break;
        case 'getHandle':
          // Forward to MAIN world via content script
          break;
      }
    } catch (err) {
      port.postMessage({ type: 'response', requestId: msg.requestId, error: err.message });
    }
  });

  port.onDisconnect.addListener(() => {
    contentPorts.delete(tabId);
  });
});

function broadcastToContentScripts(message) {
  for (const port of contentPorts.values()) {
    port.postMessage(message);
  }
}

// ──────────────────────────────────────────────────────────────
// TELEMETRY
// ──────────────────────────────────────────────────────────────
async function telemetry(outcome, capability, durationMs, errorCode) {
  const record = {
    installId,
    platform: currentFingerprint?.platform?.slug,
    fingerprintVersion: currentFingerprint?.fingerprint?.version,
    capability,
    outcome,
    durationMs,
    errorCode,
    timestamp: Date.now(),
  };

  // Queue locally
  await healthMonitor.recordTelemetry(record);

  // Send to backend via transport
  transport.sendTelemetry([record]);
}

// ──────────────────────────────────────────────────────────────
// CHROME ALARMS
// ──────────────────────────────────────────────────────────────
chrome.alarms.onAlarm.addListener(async (alarm) => {
  switch (alarm.name) {
    case 'healthCheck':
      await healthMonitor.runScheduledChecks();
      break;
    case 'telemetryFlush':
      await transport.flushTelemetry();
      break;
  }
});

// ──────────────────────────────────────────────────────────────
// TAB NAVIGATION HANDLING
// ──────────────────────────────────────────────────────────────
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    // Check if we have a fingerprint for this origin
    const fp = await fingerprintStore.getForUrl(tab.url);
    if (fp) {
      // Content script will auto-initialize via bridge
      console.log('[Metamorph] Tab navigated to fingerprinted origin:', tab.url);
    }
  }
});

// ──────────────────────────────────────────────────────────────
// INSTALL ID MANAGEMENT
// ──────────────────────────────────────────────────────────────
async function getInstallId() {
  const { installId: stored } = await chrome.storage.local.get('installId');
  if (stored) return stored;

  const newId = 'inst_' + crypto.randomUUID();
  await chrome.storage.local.set({ installId: newId });
  return newId;
}

// ──────────────────────────────────────────────────────────────
// EXTENSION LIFECYCLE
// ──────────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    console.log('[Metamorph] Extension installed');
    await initialize();
  } else if (details.reason === 'update') {
    console.log('[Metamorph] Extension updated');
    await initialize();
  }
});

chrome.runtime.onStartup.addListener(initialize);

// Handle messages from popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      let result;
      switch (msg.type) {
        case 'getStatus':
          result = {
            connected: transport.isConnected(),
            fingerprint: currentFingerprint ? {
              platform: currentFingerprint.platform?.slug,
              version: currentFingerprint.fingerprint?.version,
            } : null,
            capabilities: currentAdapter ? Object.keys(currentAdapter).filter(k => typeof currentAdapter[k] === 'function') : [],
          };
          break;
        case 'execute':
          result = await executeCapability(msg.capability, msg.args);
          break;
        case 'getHealth':
          result = await healthMonitor.getHealthReport();
          break;
      }
      sendResponse({ success: true, result });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  })();
  return true; // Async response
});

// Start initialization
initialize();
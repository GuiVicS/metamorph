/**
 * Metamorph Content Script - ISOLATED WORLD
 *
 * Runs in the content script isolated world. Can access DOM and communicate
 * with both the MAIN world (via postMessage) and the service worker (via chrome.runtime).
 */

const MESSAGE_CHANNEL = 'metamorph_bridge';
let bridgeReady = false;
let port = null;
const pendingRequests = new Map();
let messageId = 0;

// ──────────────────────────────────────────────────────────────
// COMMUNICATION WITH SERVICE WORKER
// ──────────────────────────────────────────────────────────────
function connectToWorker() {
  port = chrome.runtime.connect({ name: 'content-script' });

  port.onMessage.addListener((msg) => {
    if (msg.type === 'response') {
      const pending = pendingRequests.get(msg.requestId);
      if (pending) {
        pending.resolve(msg.result);
        pendingRequests.delete(msg.requestId);
      }
    } else if (msg.type === 'event') {
      // Forward events from worker to MAIN world
      window.postMessage({
        source: MESSAGE_CHANNEL,
        type: 'event',
        payload: msg.payload
      }, '*');
    } else if (msg.type === 'fingerprintUpdate') {
      // New fingerprint received - reinitialize
      initializeBridge(msg.fingerprint);
    }
  });

  port.onDisconnect.addListener(() => {
    console.log('[Metamorph Content] Disconnected from worker');
    port = null;
  });
}

function sendToWorker(type, payload) {
  if (!port) return Promise.reject(new Error('Not connected to worker'));
  const requestId = ++messageId;
  return new Promise((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    port.postMessage({ type, payload: { ...payload, requestId } });
    // Timeout
    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        reject(new Error('Request timeout'));
      }
    }, 30000);
  });
}

// ──────────────────────────────────────────────────────────────
// COMMUNICATION WITH MAIN WORLD (Bridge)
// ──────────────────────────────────────────────────────────────
function sendToMainWorld(type, payload) {
  window.postMessage({ source: MESSAGE_CHANNEL, type, payload }, '*');
}

window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  const msg = event.data;
  if (!msg || msg.source !== MESSAGE_CHANNEL) return;

  switch (msg.type) {
    case 'bridgeReady':
      bridgeReady = true;
      console.log('[Metamorph Content] Bridge ready');
      // Request discovery
      sendToMainWorld('discover', {});
      break;
    case 'discoveryComplete':
      console.log('[Metamorph Content] Discovery complete:', msg.payload.handles);
      sendToWorker('discoveryComplete', msg.payload);
      break;
    case 'discoveryError':
      console.error('[Metamorph Content] Discovery error:', msg.payload.error);
      sendToWorker('discoveryError', msg.payload);
      break;
    case 'response': {
      const { requestId, result, error } = msg.payload;
      const pending = pendingRequests.get(requestId);
      if (pending) {
        if (error) pending.reject(new Error(error));
        else pending.resolve(result);
        pendingRequests.delete(requestId);
      }
      break;
    }
    case 'event':
      // Forward to worker
      sendToWorker('event', msg.payload);
      break;
  }
});

// ──────────────────────────────────────────────────────────────
// BRIDGE INJECTION
// ──────────────────────────────────────────────────────────────
function injectBridge() {
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('bridge.js');
  script.onload = () => script.remove();
  (document.head || document.documentElement).appendChild(script);
}

// ──────────────────────────────────────────────────────────────
// DOM ACTOR (for dom-action bindings)
// ──────────────────────────────────────────────────────────────
async function executeDomAction(binding, args) {
  const { selector, action, valueParam = 'text', waitFor = 0 } = binding;
  const element = document.querySelector(selector);
  if (!element) throw new Error(`DOM element not found: ${selector}`);

  const value = args?.[valueParam];

  switch (action) {
    case 'click':
      element.click();
      break;
    case 'type':
      element.focus();
      // Clear existing
      element.value = '';
      element.dispatchEvent(new Event('input', { bubbles: true }));
      // Type value
      element.value = value;
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
      break;
    case 'submit':
      element.form?.requestSubmit?.();
      break;
    default:
      throw new Error(`Unknown DOM action: ${action}`);
  }

  if (waitFor > 0) await new Promise(r => setTimeout(r, waitFor));
  return { success: true };
}

// ──────────────────────────────────────────────────────────────
// MUTATION OBSERVER (for dom-read / selector verification)
// ──────────────────────────────────────────────────────────────
const observer = new MutationObserver((mutations) => {
  // Could report DOM changes to worker for selector verification
});

observer.observe(document.body, { childList: true, subtree: true, attributes: true });

// ──────────────────────────────────────────────────────────────
// INITIALIZATION
// ──────────────────────────────────────────────────────────────
function initializeBridge(fingerprint) {
  // Store fingerprint config for bridge injection
  window.__METAMORPH_FINGERPRINT__ = fingerprint;

  // Re-inject bridge (it will pick up new config)
  injectBridge();
}

// Start
connectToWorker();

// Wait for page to be ready, then inject bridge
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectBridge);
} else {
  injectBridge();
}

console.log('[Metamorph Content] Content script loaded');
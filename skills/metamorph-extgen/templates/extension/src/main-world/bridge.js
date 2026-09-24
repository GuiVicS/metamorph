/**
 * Metamorph Bridge - MAIN WORLD
 *
 * This script runs in the page's own JavaScript context (MAIN world).
 * It has access to the page's internal state (window, modules, stores).
 *
 * SECURITY CRITICAL:
 * - No eval, no Function constructor, no string-to-code sinks
 * - Path resolution is structural property access only
 * - Forbidden segments: __proto__, constructor, prototype
 * - Communicates ONLY via postMessage with structured, typed envelopes
 */

(function() {
  'use strict';

  // ──────────────────────────────────────────────────────────────
  // CONFIGURATION (injected by worker at runtime)
  // ──────────────────────────────────────────────────────────────
  const CONFIG = {
    discovery: __DISCOVERY_CONFIG__,
    handles: __HANDLES_CONFIG__,
    readyCheck: __READY_CHECK_CONFIG__,
  };

  // ──────────────────────────────────────────────────────────────
  // SECURITY: Forbidden path segments (prototype pollution prevention)
  // ──────────────────────────────────────────────────────────────
  const FORBIDDEN_SEGMENTS = new Set(['__proto__', 'constructor', 'prototype']);

  function assertSafePath(path) {
    if (!Array.isArray(path)) throw new Error('Path must be array');
    for (const seg of path) {
      if (typeof seg !== 'string') throw new Error('Path segment must be string');
      if (FORBIDDEN_SEGMENTS.has(seg)) throw new Error(`Forbidden path segment: ${seg}`);
    }
  }

  // ──────────────────────────────────────────────────────────────
  // PATH RESOLUTION - Structural traversal ONLY, no eval
  // ──────────────────────────────────────────────────────────────
  function resolvePath(root, path) {
    assertSafePath(path);
    let current = root;
    for (const segment of path) {
      if (current == null) return undefined;
      current = current[segment];
    }
    return current;
  }

  function resolvePathOrThrow(root, path) {
    const result = resolvePath(root, path);
    if (result === undefined) {
      throw new Error(`Path not found: ${path.join('.')}`);
    }
    return result;
  }

  // ──────────────────────────────────────────────────────────────
  // DISCOVERY STRATEGIES
  // ──────────────────────────────────────────────────────────────
  async function discoverWebpackChunk(injection) {
    const { chunkGlobal } = injection;
    const chunkArray = window[chunkGlobal];
    if (!chunkArray || !Array.isArray(chunkArray)) {
      throw new Error(`Webpack chunk global not found: ${chunkGlobal}`);
    }

    // Wait for webpack to be ready
    await new Promise((resolve, reject) => {
      const check = () => {
        if (chunkArray.length > 0) resolve();
        else setTimeout(check, 50);
      };
      setTimeout(() => reject(new Error('Webpack chunk timeout')), 10000);
      check();
    });

    // Extract modules by shape matching
    const modules = {};
    for (const chunk of chunkArray) {
      if (chunk && typeof chunk === 'object' && chunk[1]) {
        Object.assign(modules, chunk[1]);
      }
    }
    return modules;
  }

  async function discoverWindowPath(injection) {
    const { path } = injection;
    const obj = resolvePath(window, path);
    if (!obj) throw new Error(`Window path not found: ${path.join('.')}`);
    return obj;
  }

  async function discoverModuleByShape(modules, matchSpec) {
    const { hasKeys = [], hasMethods = [] } = matchSpec;
    for (const [id, mod] of Object.entries(modules)) {
      if (!mod || typeof mod !== 'object') continue;
      const keys = Object.keys(mod);
      const hasAllKeys = hasKeys.every(k => keys.includes(k));
      const hasAllMethods = hasMethods.every(m => typeof mod[m] === 'function');
      if (hasAllKeys && hasAllMethods) {
        return { moduleId: id, module: mod };
      }
    }
    return null;
  }

  // ──────────────────────────────────────────────────────────────
  // HANDLE RESOLUTION
  // ──────────────────────────────────────────────────────────────
  let discoveredHandles = {};
  let discoveryPromise = null;

  async function runDiscovery() {
    if (discoveryPromise) return discoveryPromise;

    discoveryPromise = (async () => {
      const strategies = [...CONFIG.discovery].sort((a, b) => (a.priority || 99) - (b.priority || 99));
      const allModules = {};

      for (const strategy of strategies) {
        try {
          let result;
          switch (strategy.strategy) {
            case 'webpack-chunk-injection':
              result = await discoverWebpackChunk(strategy);
              Object.assign(allModules, result);
              break;
            case 'window-path':
              result = await discoverWindowPath(strategy);
              allModules[strategy.id] = result;
              break;
            default:
              console.warn('[Metamorph] Unknown discovery strategy:', strategy.strategy);
          }
        } catch (e) {
          console.warn('[Metamorph] Discovery strategy failed:', strategy.id, e);
        }
      }

      // Resolve handles by shape matching
      for (const [handleName, handleConfig] of Object.entries(CONFIG.handles)) {
        const { via, moduleMatch } = handleConfig;
        const source = allModules[via] || allModules;
        if (!source) {
          console.warn('[Metamorph] Handle source not found:', via);
          continue;
        }
        const matched = await discoverModuleByShape(source, moduleMatch);
        if (matched) {
          discoveredHandles[handleName] = matched.module;
          console.log('[Metamorph] Handle resolved:', handleName, 'via', via);
        } else {
          console.warn('[Metamorph] Handle NOT resolved:', handleName, 'match:', moduleMatch);
        }
      }

      return discoveredHandles;
    })();

    return discoveryPromise;
  }

  // ──────────────────────────────────────────────────────────────
  // READY CHECK
  // ──────────────────────────────────────────────────────────────
  async function waitForReady() {
    const { type, condition, intervalMs = 100, timeoutMs = 15000 } = CONFIG.readyCheck;
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      let ready = false;
      switch (type) {
        case 'poll':
          if (condition.handleExists) {
            ready = !!discoveredHandles[condition.handleExists];
          }
          break;
      }
      if (ready) return true;
      await new Promise(r => setTimeout(r, intervalMs));
    }
    throw new Error('Ready check timeout');
  }

  // ──────────────────────────────────────────────────────────────
  // INTERCEPTORS
  // ──────────────────────────────────────────────────────────────
  const interceptors = {
    fetch: [],
    xhr: [],
    websocket: [],
    function: new Map(),
  };

  function installFetchInterceptor(matchSpec, callback) {
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
      const response = await originalFetch.apply(this, args);
      // Check match
      try {
        const url = args[0];
        if (matchSpec.urlPattern && !url.includes(matchSpec.urlPattern)) return response;
        if (matchSpec.method && args[1]?.method !== matchSpec.method) return response;
        // Clone response for reading
        const clone = response.clone();
        const body = await clone.json().catch(() => clone.text().catch(() => null));
        callback({ url, method: args[1]?.method || 'GET', response: body });
      } catch (e) {
        // Ignore interceptor errors
      }
      return response;
    };
    interceptors.fetch.push({ matchSpec, callback });
  }

  function installWebSocketInterceptor(matchSpec, callback) {
    const OriginalWS = window.WebSocket;
    window.WebSocket = function(url, protocols) {
      const ws = new OriginalWS(url, protocols);
      const originalOnMessage = ws.onmessage;
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (matchSpec.match) {
            const matchPath = matchSpec.match.path || ['t'];
            const matchValue = matchSpec.match.equals;
            const value = resolvePath(data, matchPath);
            if (value === matchValue) {
              const payload = matchSpec.payloadPath ? resolvePath(data, matchSpec.payloadPath) : data;
              callback(payload);
            }
          }
        } catch (e) {}
        if (originalOnMessage) originalOnMessage.call(ws, event);
      };
      return ws;
    };
    interceptors.websocket.push({ matchSpec, callback });
  }

  function installFunctionInterceptor(targetPath, methodName, callback) {
    const target = resolvePath(window, targetPath);
    if (!target || typeof target[methodName] !== 'function') return false;

    const original = target[methodName];
    const wrapped = function(...args) {
      const result = original.apply(this, args);
      try {
        callback({ method: methodName, args, result, this: this });
      } catch (e) {}
      return result;
    };
    target[methodName] = wrapped;
    interceptors.function.set(`${targetPath}.${methodName}`, { original, wrapped });
    return true;
  }

  // ──────────────────────────────────────────────────────────────
  // MESSAGE PROTOCOL (postMessage to ISOLATED world)
  // ──────────────────────────────────────────────────────────────
  const MESSAGE_CHANNEL = 'metamorph_bridge';
  let messageId = 0;
  const pendingRequests = new Map();

  function sendToWorker(type, payload) {
    window.postMessage({ source: MESSAGE_CHANNEL, type, payload }, '*');
  }

  function sendResponse(requestId, result, error) {
    window.postMessage({
      source: MESSAGE_CHANNEL,
      type: 'response',
      payload: { requestId, result, error: error?.message }
    }, '*');
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || msg.source !== MESSAGE_CHANNEL) return;

    switch (msg.type) {
      case 'invoke': {
        const { requestId, capability, binding, args } = msg.payload;
        handleInvoke(requestId, capability, binding, args);
        break;
      }
      case 'subscribe': {
        const { requestId, capability, binding } = msg.payload;
        handleSubscribe(requestId, capability, binding);
        break;
      }
      case 'getHandle': {
        const { requestId, handleName } = msg.payload;
        const handle = discoveredHandles[handleName];
        sendResponse(requestId, handle ? { found: true } : { found: false });
        break;
      }
      case 'discover': {
        runDiscovery().then(() => waitForReady())
          .then(() => sendToWorker('discoveryComplete', { handles: Object.keys(discoveredHandles) }))
          .catch(err => sendToWorker('discoveryError', { error: err.message }));
        break;
      }
    }
  });

  // ──────────────────────────────────────────────────────────────
  // CAPABILITY EXECUTION
  // ──────────────────────────────────────────────────────────────
  async function handleInvoke(requestId, capability, binding, args) {
    try {
      let result;
      switch (binding.type) {
        case 'runtime-call': {
          const handle = discoveredHandles[binding.handle];
          if (!handle) throw new Error(`Handle not found: ${binding.handle}`);
          const method = handle[binding.method];
          if (typeof method !== 'function') throw new Error(`Method not found: ${binding.method}`);
          const resolvedArgs = (binding.args || []).map(arg => resolveArg(arg, args));
          result = await method.apply(handle, resolvedArgs);
          if (binding.resultPath) result = resolvePath(result, binding.resultPath);
          break;
        }
        case 'runtime-read': {
          const handle = discoveredHandles[binding.handle];
          if (!handle) throw new Error(`Handle not found: ${binding.handle}`);
          result = binding.path ? resolvePath(handle, binding.path) : handle;
          break;
        }
        case 'internal-http': {
          const url = interpolateTemplate(binding.urlTemplate, args);
          const headers = { ...binding.headers };
          const body = binding.body ? buildBody(binding.body, args) : undefined;
          const response = await fetch(url, {
            method: binding.method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
            credentials: binding.credentials || 'same-origin',
          });
          result = await response.json().catch(() => response.text().catch(() => null));
          break;
        }
        case 'dom-action': {
          result = await executeDomAction(binding, args);
          break;
        }
        default:
          throw new Error(`Unsupported binding type: ${binding.type}`);
      }
      sendResponse(requestId, result);
    } catch (err) {
      sendResponse(requestId, null, err);
    }
  }

  function handleSubscribe(requestId, capability, binding) {
    try {
      let unsubscribe;
      switch (binding.type) {
        case 'runtime-subscribe': {
          const handle = discoveredHandles[binding.handle];
          if (!handle) throw new Error(`Handle not found: ${binding.handle}`);
          const subMethod = handle[binding.subscribeMethod];
          const unsubMethod = handle[binding.unsubscribeMethod];
          if (typeof subMethod !== 'function' || typeof unsubMethod !== 'function') {
            throw new Error('Subscribe/unsubscribe methods not found');
          }
          unsubscribe = subMethod.call(handle, (data) => {
            const result = binding.readMethod ? handle[binding.readMethod]() : data;
            sendToWorker('event', { capability, requestId, data: result });
          });
          break;
        }
        case 'network-intercept':
        case 'function-intercept':
          // Handled by interceptors above
          unsubscribe = () => {};
          break;
        default:
          throw new Error(`Unsupported subscription type: ${binding.type}`);
      }
      sendResponse(requestId, { subscribed: true, unsubscribeToken: requestId });
    } catch (err) {
      sendResponse(requestId, null, err);
    }
  }

  // ──────────────────────────────────────────────────────────────
  // HELPERS
  // ──────────────────────────────────────────────────────────────
  function resolveArg(argSpec, contextArgs) {
    if (!argSpec || typeof argSpec !== 'object') return argSpec;
    if (argSpec.from?.startsWith('param:')) {
      const key = argSpec.from.slice(6);
      return contextArgs?.[key];
    }
    if (argSpec.transform === 'generateNonce') {
      return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
    return argSpec;
  }

  function interpolateTemplate(template, args) {
    return template.replace(/\{(\w+)\}/g, (_, key) => args?.[key] ?? '');
  }

  function buildBody(bodySpec, args) {
    const result = {};
    for (const [key, spec] of Object.entries(bodySpec)) {
      result[key] = resolveArg(spec, args);
    }
    return result;
  }

  async function executeDomAction(binding, args) {
    const selector = binding.selector;
    const action = binding.action; // 'click', 'type', 'submit'
    const value = args?.[binding.valueParam || 'text'];

    const element = document.querySelector(selector);
    if (!element) throw new Error(`Element not found: ${selector}`);

    switch (action) {
      case 'click':
        element.click();
        return { clicked: true };
      case 'type':
        element.focus();
        element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return { typed: true };
      case 'submit':
        element.form?.requestSubmit?.();
        return { submitted: true };
      default:
        throw new Error(`Unknown DOM action: ${action}`);
    }
  }

  // ──────────────────────────────────────────────────────────────
  // INITIALIZATION
  // ──────────────────────────────────────────────────────────────
  console.log('[Metamorph] Bridge loaded, awaiting discovery...');

  // Signal ready to worker
  sendToWorker('bridgeReady', { timestamp: Date.now() });

  // Export for debugging
  window.__METAMORPH_BRIDGE__ = {
    discoveredHandles: () => discoveredHandles,
    runDiscovery,
    waitForReady,
  };
})();
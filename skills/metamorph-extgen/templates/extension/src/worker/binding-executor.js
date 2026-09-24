/**
 * Binding Executor - Executes capability bindings
 */

export class BindingExecutor {
  constructor() {
    this.subscriptions = new Map();
  }

  async execute(binding, args, fingerprint) {
    switch (binding.type) {
      case 'runtime-call':
        return this._executeRuntimeCall(binding, args, fingerprint);
      case 'runtime-read':
        return this._executeRuntimeRead(binding, args, fingerprint);
      case 'internal-http':
        return this._executeInternalHttp(binding, args, fingerprint);
      case 'graphql':
        return this._executeGraphQL(binding, args, fingerprint);
      case 'dom-action':
        return this._executeDomAction(binding, args);
      case 'dom-read':
        return this._executeDomRead(binding, args);
      default:
        throw new Error(`Unknown binding type: ${binding.type}`);
    }
  }

  async _executeRuntimeCall(binding, args, fingerprint) {
    // This executes in MAIN world via content script bridge
    const handle = fingerprint.runtime?.handles?.[binding.handle];
    if (!handle) throw new Error(`Handle not found: ${binding.handle}`);

    // Send to content script which forwards to MAIN world
    return this._sendToMainWorld('invoke', {
      capability: binding.handle + '.' + binding.method,
      binding: { type: 'runtime-call', handle: binding.handle, method: binding.method, args: binding.args || [], resultPath: binding.resultPath },
      args,
    });
  }

  async _executeRuntimeRead(binding, args, fingerprint) {
    return this._sendToMainWorld('invoke', {
      capability: binding.handle + '.' + (binding.path || ''),
      binding: { type: 'runtime-read', handle: binding.handle, path: binding.path },
      args,
    });
  }

  async _executeInternalHttp(binding, args, fingerprint) {
    const url = this._interpolateTemplate(binding.urlTemplate, args);
    const headers = { ...binding.headers };
    const body = binding.body ? this._buildBody(binding.body, args) : undefined;

    const response = await fetch(url, {
      method: binding.method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: binding.credentials || 'same-origin',
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return response.json();
    }
    return response.text();
  }

  async _executeGraphQL(binding, args, fingerprint) {
    const url = binding.urlTemplate || '/graphql';
    const variables = this._buildBody(binding.variables || {}, args);

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...binding.headers },
      body: JSON.stringify({ query: binding.query, variables }),
      credentials: binding.credentials || 'same-origin',
    });

    const result = await response.json();
    if (result.errors) throw new Error(result.errors[0].message);
    return binding.resultPath ? this._resolvePath(result, binding.resultPath) : result.data;
  }

  async _executeDomAction(binding, args) {
    return this._sendToContentScript('dom-action', { binding, args });
  }

  async _executeDomRead(binding, args) {
    return this._sendToContentScript('dom-read', { binding, args });
  }

  subscribe(binding, handler, fingerprint) {
    const key = JSON.stringify(binding);
    if (!this.subscriptions.has(key)) {
      this.subscriptions.set(key, new Set());
    }
    this.subscriptions.get(key).add(handler);

    // Set up the actual subscription based on binding type
    if (binding.type === 'runtime-subscribe') {
      this._subscribeRuntime(binding, handler, fingerprint);
    } else if (binding.type === 'network-intercept' || binding.type === 'function-intercept') {
      this._subscribeIntercept(binding, handler);
    }
  }

  unsubscribe(binding, handler) {
    const key = JSON.stringify(binding);
    const handlers = this.subscriptions.get(key);
    if (handlers) handlers.delete(handler);
  }

  _subscribeRuntime(binding, handler, fingerprint) {
    this._sendToMainWorld('subscribe', {
      capability: binding.handle,
      binding: { type: 'runtime-subscribe', handle: binding.handle, ...binding },
    });
  }

  _subscribeIntercept(binding, handler) {
    // Set up interceptors in MAIN world
    this._sendToMainWorld('subscribe', { binding, handlerId: handler.toString() });
  }

  _sendToMainWorld(type, payload) {
    return new Promise((resolve, reject) => {
      // This would be implemented via chrome.runtime.sendMessage to content script
      // which then postMessages to MAIN world
      console.log('[BindingExecutor] Send to MAIN world:', type, payload);
      resolve({ mocked: true });
    });
  }

  _sendToContentScript(type, payload) {
    return new Promise((resolve, reject) => {
      console.log('[BindingExecutor] Send to content script:', type, payload);
      resolve({ mocked: true });
    });
  }

  _interpolateTemplate(template, args) {
    return template.replace(/\{(\w+)\}/g, (_, key) => args?.[key] ?? '');
  }

  _buildBody(bodySpec, args) {
    const result = {};
    for (const [key, spec] of Object.entries(bodySpec)) {
      result[key] = this._resolveArg(spec, args);
    }
    return result;
  }

  _resolveArg(spec, args) {
    if (!spec || typeof spec !== 'object') return spec;
    if (spec.from?.startsWith('param:')) {
      return args?.[spec.from.slice(6)];
    }
    if (spec.transform === 'generateNonce') {
      return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
    if (spec.constant !== undefined) return spec.constant;
    return spec;
  }

  _resolvePath(obj, path) {
    if (!Array.isArray(path)) return obj;
    let current = obj;
    for (const segment of path) {
      if (current == null) return undefined;
      current = current[segment];
    }
    return current;
  }
}
/**
 * Adapter Engine - Builds ChannelAdapter from Fingerprint
 */

import { BindingExecutor } from './binding-executor.js';
import { Normalizer } from './normalizer.js';
import { EventBus } from './event-bus.js';

export class AdapterEngine {
  constructor() {
    this.bindingExecutor = new BindingExecutor();
    this.normalizer = new Normalizer();
    this.eventBus = new EventBus();
  }

  async build(fingerprint) {
    const adapter = {
      platform: fingerprint.platform?.slug,
      fingerprintVersion: fingerprint.fingerprint?.version,
      _fingerprint: fingerprint,
      _executors: {},
      _eventSubscriptions: new Map(),
    };

    // Build capability methods
    for (const [capName, capDef] of Object.entries(fingerprint.capabilities || {})) {
      if (!capDef.supported) {
        adapter[capName] = () => Promise.reject(new Error(`Unsupported capability: ${capName}`));
        continue;
      }
      adapter[capName] = this._createCapabilityExecutor(capName, capDef, fingerprint);
    }

    // Build event subscriptions
    for (const [eventName, eventDef] of Object.entries(fingerprint.events || {})) {
      if (!eventDef.supported) continue;
      adapter.on = adapter.on || ((event, cb) => this._subscribeEvent(adapter, event, cb, eventDef, fingerprint));
    }

    // Introspection methods
    adapter.supports = (cap) => !!fingerprint.capabilities?.[cap]?.supported;
    adapter.health = () => this._healthCheck(fingerprint);

    // Session methods
    adapter.isAuthenticated = () => this._executeCapability('isAuthenticated', fingerprint, {});
    adapter.getAccount = () => this._executeCapability('getAccount', fingerprint, {});
    adapter.getConnectionState = () => this._executeCapability('getConnectionState', fingerprint, {});

    return adapter;
  }

  _createCapabilityExecutor(capName, capDef, fingerprint) {
    return async (args = {}) => {
      const binding = capDef.binding;
      if (!binding) throw new Error(`No binding for capability: ${capName}`);

      // Execute via binding executor
      const rawResult = await this.bindingExecutor.execute(binding, args, fingerprint);

      // Normalize
      if (capDef.returns?.entity) {
        return this.normalizer.normalizeEntity(
          capDef.returns.entity,
          rawResult,
          fingerprint.entities?.[capDef.returns.entity]?.mapping,
          capDef.returns.cardinality
        );
      }

      return rawResult;
    };
  }

  async _executeCapability(capName, fingerprint, args) {
    const capDef = fingerprint.capabilities?.[capName];
    if (!capDef?.supported) throw new Error(`Unsupported: ${capName}`);
    return this._createCapabilityExecutor(capName, capDef, fingerprint)(args);
  }

  _subscribeEvent(adapter, eventName, callback, eventDef, fingerprint) {
    const binding = eventDef.binding;
    const entity = eventDef.entity;

    const handler = (rawData) => {
      const normalized = this.normalizer.normalizeEntity(entity, rawData, fingerprint.entities?.[entity]?.mapping, 'one');
      callback(normalized);
    };

    // Execute subscription binding
    this.bindingExecutor.subscribe(binding, handler, fingerprint);

    // Return unsubscribe function
    return () => {
      this.bindingExecutor.unsubscribe(binding, handler);
    };
  }

  async _healthCheck(fingerprint) {
    const results = {};
    for (const [capName, capDef] of Object.entries(fingerprint.capabilities || {})) {
      if (!capDef.supported) {
        results[capName] = { status: 'unsupported' };
        continue;
      }
      if (capDef.binding?.type === 'dom-action' || capDef.binding?.type === 'dom-read') {
        results[capName] = { status: 'degraded', reason: 'DOM binding' };
        continue;
      }
      try {
        await this._executeCapability(capName, fingerprint, {});
        results[capName] = { status: 'ok' };
      } catch (err) {
        results[capName] = { status: 'failing', error: err.message };
      }
    }
    return {
      platform: fingerprint.platform?.slug,
      fingerprintVersion: fingerprint.fingerprint?.version,
      checkedAt: Date.now(),
      overall: Object.values(results).every(r => r.status === 'ok') ? 'healthy' :
               Object.values(results).some(r => r.status === 'failing') ? 'broken' : 'degraded',
      capabilities: results,
    };
  }
}
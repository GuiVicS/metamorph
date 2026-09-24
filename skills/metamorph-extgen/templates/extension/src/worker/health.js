/**
 * Health Monitor - Probe runner, telemetry collection
 */

import { eventBus, Events } from './event-bus.js';

export class HealthMonitor {
  constructor() {
    this.telemetryQueue = [];
    this.probeResults = new Map();
  }

  start() {
    // Periodic health checks
    setInterval(() => this.runScheduledChecks(), 5 * 60 * 1000); // Every 5 min
  }

  async runProbes(fingerprint, options = {}) {
    const results = {};
    for (const probe of fingerprint.probes || []) {
      if (options.onlyRead && probe.sideEffects === 'writes') continue;
      if (probe.runOn && !probe.runOn.includes(options.context || 'health')) continue;

      try {
        const result = await this._runProbe(probe, fingerprint);
        results[probe.id] = { passed: true, result };
      } catch (err) {
        results[probe.id] = { passed: false, error: err.message };
      }
    }
    return results;
  }

  async _runProbe(probe, fingerprint) {
    // Execute probe steps
    for (const step of probe.steps) {
      if (step.invoke) {
        // Would execute capability via adapter
        console.log('[HealthMonitor] Probe step:', step);
      }
    }
    return { success: true };
  }

  async runScheduledChecks() {
    // Run read-only probes for all active fingerprints
    console.log('[HealthMonitor] Running scheduled health checks');
    // Implementation would iterate over active fingerprints
  }

  async recordTelemetry(record) {
    this.telemetryQueue.push(record);
    // Keep queue bounded
    if (this.telemetryQueue.length > 1000) {
      this.telemetryQueue = this.telemetryQueue.slice(-500);
    }
  }

  getTelemetry() {
    return this.telemetryQueue;
  }

  async getHealthReport() {
    // Aggregate telemetry into health report
    const now = Date.now();
    const recent = this.telemetryQueue.filter(t => now - t.timestamp < 3600000); // Last hour

    const byCapability = {};
    for (const t of recent) {
      if (!byCapability[t.capability]) {
        byCapability[t.capability] = { ok: 0, error: 0 };
      }
      byCapability[t.capability][t.outcome]++;
    }

    const capabilities = {};
    for (const [cap, counts] of Object.entries(byCapability)) {
      const total = counts.ok + counts.error;
      capabilities[cap] = {
        status: counts.error === 0 ? 'ok' : counts.error / total > 0.5 ? 'failing' : 'degraded',
        lastSuccessAt: recent.filter(t => t.capability === cap && t.outcome === 'ok').pop()?.timestamp,
        lastFailureAt: recent.filter(t => t.capability === cap && t.outcome === 'error').pop()?.timestamp,
        errorRate1h: total > 0 ? counts.error / total : 0,
      };
    }

    return {
      platform: 'unknown',
      fingerprintVersion: 'unknown',
      checkedAt: now,
      overall: Object.values(capabilities).some(c => c.status === 'failing') ? 'broken' :
               Object.values(capabilities).some(c => c.status === 'degraded') ? 'degraded' : 'healthy',
      capabilities,
    };
  }
}
/**
 * Transport - WebSocket communication with backend
 */

const RECONNECT_BASE_MS = 1000;
const MAX_RECONNECT_MS = 30000;

export class Transport {
  constructor() {
    this.ws = null;
    this.url = null;
    this.installId = null;
    this.messageHandlers = new Map();
    this.reconnectAttempts = 0;
    this.connected = false;
    this.pendingAcks = new Map();
    this.telemetryBuffer = [];
  }

  async register(installId) {
    this.installId = installId;
    // In real implementation, this would be an HTTP POST to /instances/register
    // For now, return mock
    return { instanceId: 'inst_' + crypto.randomUUID(), backendWsUrl: 'wss://api.metamorph.dev/v1/ws' };
  }

  async connect(backendUrl, installId, onMessage) {
    this.url = backendUrl;
    this.installId = installId;
    this.onMessage = onMessage;

    return this._connect();
  }

  _connect() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[Transport] Connected');
          this.connected = true;
          this.reconnectAttempts = 0;
          this._sendHello();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            this._handleMessage(msg);
          } catch (err) {
            console.error('[Transport] Message parse error:', err);
          }
        };

        this.ws.onclose = () => {
          console.log('[Transport] Disconnected');
          this.connected = false;
          this._scheduleReconnect();
        };

        this.ws.onerror = (err) => {
          console.error('[Transport] Error:', err);
          if (!this.connected) reject(err);
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  _sendHello() {
    this.send({ t: 'hello', installId: this.installId, runtimeVersion: '1.0.0' });
  }

  _handleMessage(msg) {
    switch (msg.t) {
      case 'welcome':
        console.log('[Transport] Welcome:', msg.instanceId);
        break;
      case 'fingerprint.update':
      case 'fingerprint.rollback':
      case 'probe.request':
        if (this.onMessage) this.onMessage(msg);
        break;
      case 'ack':
        const pending = this.pendingAcks.get(msg.id);
        if (pending) {
          pending.resolve();
          this.pendingAcks.delete(msg.id);
        }
        break;
      case 'ping':
        this.send({ t: 'pong' });
        break;
    }
  }

  _scheduleReconnect() {
    const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempts), MAX_RECONNECT_MS);
    this.reconnectAttempts++;
    console.log(`[Transport] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this._connect(), delay);
  }

  send(msg) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.telemetryBuffer.push(msg);
      return false;
    }
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  sendWithAck(msg, timeoutMs = 5000) {
    const id = 'msg_' + crypto.randomUUID();
    const msgWithId = { ...msg, id };
    return new Promise((resolve, reject) => {
      this.pendingAcks.set(id, { resolve, reject });
      this.send(msgWithId);
      setTimeout(() => {
        if (this.pendingAcks.has(id)) {
          this.pendingAcks.delete(id);
          reject(new Error('Ack timeout'));
        }
      }, timeoutMs);
    });
  }

  sendTelemetry(events) {
    if (events.length === 0) return;
    this.send({ t: 'telemetry', events });
  }

  async flushTelemetry() {
    // Already sent via sendTelemetry
  }

  isConnected() {
    return this.connected;
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
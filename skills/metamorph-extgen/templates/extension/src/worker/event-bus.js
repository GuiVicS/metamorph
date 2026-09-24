/**
 * Event Bus - Deduplication, ordering, fan-out
 */

const DEDUPE_WINDOW_MS = 60000; // 60 seconds

export class EventBus {
  constructor() {
    this.handlers = new Map(); // eventName -> Set<handler>
    this.dedupeCache = new Map(); // eventKey -> timestamp
  }

  on(eventName, handler) {
    if (!this.handlers.has(eventName)) {
      this.handlers.set(eventName, new Set());
    }
    this.handlers.get(eventName).add(handler);

    return () => this.off(eventName, handler);
  }

  off(eventName, handler) {
    const handlers = this.handlers.get(eventName);
    if (handlers) handlers.delete(handler);
  }

  emit(eventName, data, dedupeKey) {
    // Deduplication
    if (dedupeKey) {
      const now = Date.now();
      const key = `${eventName}:${dedupeKey}`;
      const lastSeen = this.dedupeCache.get(key);
      if (lastSeen && now - lastSeen < DEDUPE_WINDOW_MS) {
        return false; // Duplicate suppressed
      }
      this.dedupeCache.set(key, now);
      // Clean old entries
      for (const [k, ts] of this.dedupeCache.entries()) {
        if (now - ts > DEDUPE_WINDOW_MS) this.dedupeCache.delete(k);
      }
    }

    const handlers = this.handlers.get(eventName);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(data);
        } catch (err) {
          console.error('[EventBus] Handler error:', err);
        }
      }
    }
    return true;
  }

  clear() {
    this.handlers.clear();
    this.dedupeCache.clear();
  }
}

// Global event bus instance
export const eventBus = new EventBus();

// Standard event names
export const Events = {
  MESSAGE_RECEIVED: 'message.received',
  MESSAGE_SENT: 'message.sent',
  MESSAGE_UPDATED: 'message.updated',
  CONVERSATION_UPDATED: 'conversation.updated',
  CONNECTION_CHANGED: 'connection.changed',
};
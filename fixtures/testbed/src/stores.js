// Message Store - manages messages for conversations
class MessageStore {
    constructor() {
        this.messages = new Map(); // conversationId -> Message[]
        this.listeners = new Set();
        this._initializeDemoData();
    }

    _initializeDemoData() {
        // Demo conversations with messages
        const now = Date.now();
        this.messages.set('conv_1', [
            { id: 'msg_1', conversationId: 'conv_1', authorId: 'user_2', content: 'Hey! Are we still on for 6pm?', timestamp: now - 3600000, edited: false },
            { id: 'msg_2', conversationId: 'conv_1', authorId: 'user_1', content: 'Yes, see you there!', timestamp: now - 3500000, edited: false },
            { id: 'msg_3', conversationId: 'conv_1', authorId: 'user_2', content: 'Great, I\'ll bring the wine', timestamp: now - 3400000, edited: false },
        ]);
        this.messages.set('conv_2', [
            { id: 'msg_4', conversationId: 'conv_2', authorId: 'user_3', content: 'Meeting moved to 3pm', timestamp: now - 7200000, edited: false },
            { id: 'msg_5', conversationId: 'conv_2', authorId: 'user_1', content: 'Got it, thanks', timestamp: now - 7100000, edited: false },
        ]);
        this.messages.set('conv_3', [
            { id: 'msg_6', conversationId: 'conv_3', authorId: 'user_4', content: 'Welcome to the channel!', timestamp: now - 86400000, edited: false },
            { id: 'msg_7', conversationId: 'conv_3', authorId: 'user_5', content: 'Thanks! Excited to be here', timestamp: now - 86300000, edited: false },
        ]);
        this.messages.set('conv_4', [
            { id: 'msg_8', conversationId: 'conv_4', authorId: 'user_1', content: 'Hey team, quick update', timestamp: now - 1800000, edited: false },
        ]);
    }

    getMessages(conversationId) {
        return this.messages.get(conversationId) || [];
    }

    getMessage(messageId) {
        for (const msgs of this.messages.values()) {
            const msg = msgs.find(m => m.id === messageId);
            if (msg) return msg;
        }
        return null;
    }

    addMessage(conversationId, message) {
        if (!this.messages.has(conversationId)) {
            this.messages.set(conversationId, []);
        }
        this.messages.get(conversationId).push(message);
        this._notify();
        return message;
    }

    editMessage(messageId, newContent) {
        for (const msgs of this.messages.values()) {
            const msg = msgs.find(m => m.id === messageId);
            if (msg) {
                msg.content = newContent;
                msg.edited = true;
                msg.editedAt = Date.now();
                this._notify();
                return msg;
            }
        }
        return null;
    }

    deleteMessage(messageId) {
        for (const [convId, msgs] of this.messages.entries()) {
            const idx = msgs.findIndex(m => m.id === messageId);
            if (idx !== -1) {
                msgs.splice(idx, 1);
                this._notify();
                return true;
            }
        }
        return false;
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    _notify() {
        for (const listener of this.listeners) {
            listener(this.messages);
        }
    }
}

// Channel/Conversation Store
class ChannelStore {
    constructor() {
        this.channels = new Map();
        this.listeners = new Set();
        this._initializeDemoData();
    }

    _initializeDemoData() {
        const now = Date.now();
        this.channels.set('conv_1', {
            id: 'conv_1', type: 1, name: null, participants: ['user_1', 'user_2'],
            lastMessageAt: now - 3400000, unreadCount: 0,
        });
        this.channels.set('conv_2', {
            id: 'conv_2', type: 1, name: null, participants: ['user_1', 'user_3'],
            lastMessageAt: now - 7100000, unreadCount: 2,
        });
        this.channels.set('conv_3', {
            id: 'conv_3', type: 0, name: 'general', participants: ['user_1', 'user_4', 'user_5', 'user_6'],
            lastMessageAt: now - 86300000, unreadCount: 5,
        });
        this.channels.set('conv_4', {
            id: 'conv_4', type: 2, name: 'team-updates', participants: ['user_1', 'user_2', 'user_3', 'user_7'],
            lastMessageAt: now - 1800000, unreadCount: 1,
        });
    }

    getChannel(id) {
        return this.channels.get(id) || null;
    }

    getAllChannels() {
        return Array.from(this.channels.values());
    }

    getDMFromUserId(userId) {
        for (const ch of this.channels.values()) {
            if (ch.type === 1 && ch.participants.includes(userId)) {
                return ch;
            }
        }
        return null;
    }

    createChannel(data) {
        const id = 'conv_' + Date.now();
        const channel = { id, ...data, lastMessageAt: Date.now(), unreadCount: 0 };
        this.channels.set(id, channel);
        this._notify();
        return channel;
    }

    updateChannel(id, data) {
        const ch = this.channels.get(id);
        if (ch) {
            Object.assign(ch, data);
            this._notify();
            return ch;
        }
        return null;
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    _notify() {
        for (const listener of this.listeners) {
            listener(this.channels);
        }
    }
}

// Current User Store
class CurrentUserStore {
    constructor() {
        this.currentUser = {
            id: 'user_1',
            username: 'alex_dev',
            global_name: 'Alex Developer',
            avatar: null,
            email: 'alex@example.com',
        };
        this.listeners = new Set();
    }

    getCurrentUser() {
        return this.currentUser;
    }

    setCurrentUser(user) {
        this.currentUser = user;
        this._notify();
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    _notify() {
        for (const listener of this.listeners) {
            listener(this.currentUser);
        }
    }
}

// Connection Store
class ConnectionStore {
    constructor() {
        this.state = 'connected';
        this.listeners = new Set();
        // Simulate occasional reconnection
        setInterval(() => {
            if (Math.random() < 0.01) {
                this.state = 'connecting';
                this._notify();
                setTimeout(() => {
                    this.state = 'connected';
                    this._notify();
                }, 1000);
            }
        }, 30000);
    }

    isConnected() {
        return this.state === 'connected';
    }

    getState() {
        return this.state;
    }

    addChangeListener(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    removeChangeListener(listener) {
        this.listeners.delete(listener);
    }

    _notify() {
        for (const listener of this.listeners) {
            listener(this.state);
        }
    }
}

// WebSocket Manager (simulated)
class WebSocketManager {
    constructor() {
        this.handlers = new Map();
        this.connected = false;
        this._simulateConnection();
    }

    _simulateConnection() {
        this.connected = true;
        // Simulate incoming messages every 10-30 seconds
        setInterval(() => {
            if (this.connected && Math.random() < 0.3) {
                this._simulateIncomingMessage();
            }
        }, 15000);
    }

    _simulateIncomingMessage() {
        const conversations = ['conv_1', 'conv_2', 'conv_3', 'conv_4'];
        const convId = conversations[Math.floor(Math.random() * conversations.length)];
        const authors = ['user_2', 'user_3', 'user_4', 'user_5'];
        const authorId = authors[Math.floor(Math.random() * authors.length)];
        const messages = [
            'Hey, quick question',
            'Did you see the update?',
            'Let me check on that',
            'Sounds good to me',
            'I\'ll get back to you',
        ];
        const content = messages[Math.floor(Math.random() * messages.length)];

        const msg = {
            t: 'MESSAGE_CREATE',
            d: {
                id: 'msg_' + Date.now(),
                conversationId: convId,
                authorId: authorId,
                content: content,
                timestamp: new Date().toISOString(),
                edited: false,
            },
        };

        const handler = this.handlers.get('MESSAGE_CREATE');
        if (handler) handler(msg);
    }

    on(event, handler) {
        this.handlers.set(event, handler);
    }

    off(event) {
        this.handlers.delete(event);
    }

    send(data) {
        // Simulate sending
        console.log('[WS] Sending:', data);
        return Promise.resolve({ success: true });
    }
}

// Export stores as a module system (webpack-like)
const messageStore = new MessageStore();
const channelStore = new ChannelStore();
const currentUserStore = new CurrentUserStore();
const connectionStore = new ConnectionStore();
const wsManager = new WebSocketManager();

// Simulate webpack module registration
window.webpackChunktestbed_app = window.webpackChunktestbed_app || [];
window.webpackChunktestbed_app.push([
    ['stores'],
    {},
    (require) => {
        require.d(require, {
            getMessageStore: () => messageStore,
            getChannelStore: () => channelStore,
            getCurrentUserStore: () => currentUserStore,
            getConnectionStore: () => connectionStore,
            getWebSocketManager: () => wsManager,
        });
    },
]);

// Also expose on window for direct access
window.TestbedStores = {
    messageStore,
    channelStore,
    currentUserStore,
    connectionStore,
    wsManager,
};

// Internal API functions (simulating same-origin fetch)
window.TestbedAPI = {
    async getConversations() {
        const channels = channelStore.getAllChannels();
        return channels.map(c => ({
            id: c.id,
            type: c.type,
            name: c.name,
            participants: c.participants,
            lastMessageAt: c.lastMessageAt,
            unreadCount: c.unreadCount,
        }));
    },

    async getMessages(conversationId, params = {}) {
        let msgs = messageStore.getMessages(conversationId);
        if (params.before) {
            const beforeId = params.before;
            const idx = msgs.findIndex(m => m.id === beforeId);
            if (idx !== -1) msgs = msgs.slice(0, idx);
        }
        const limit = params.limit || 50;
        return msgs.slice(-limit);
    },

    async sendMessage(conversationId, content) {
        const user = currentUserStore.getCurrentUser();
        const message = {
            id: 'msg_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8),
            conversationId,
            authorId: user.id,
            content,
            timestamp: Date.now(),
            edited: false,
        };
        messageStore.addMessage(conversationId, message);

        // Update channel
        const ch = channelStore.getChannel(conversationId);
        if (ch) {
            ch.lastMessageAt = message.timestamp;
            channelStore.updateChannel(conversationId, { lastMessageAt: message.timestamp });
        }

        return message;
    },

    async markAsRead(conversationId) {
        const ch = channelStore.getChannel(conversationId);
        if (ch) {
            ch.unreadCount = 0;
            channelStore.updateChannel(conversationId, { unreadCount: 0 });
        }
        return { success: true };
    },
};

export { messageStore, channelStore, currentUserStore, connectionStore, wsManager };
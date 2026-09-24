// Message Store - manages messages for conversations (v2: renamed exports)
class MessageStore {
    constructor() {
        this._messages = new Map(); // conversationId -> Message[]
        this._listeners = new Set();
        this._initializeDemoData();
    }

    _initializeDemoData() {
        const now = Date.now();
        this._messages.set('conv_1', [
            { id: 'msg_1', conversationId: 'conv_1', authorId: 'user_2', content: 'Hey! Are we still on for 6pm?', timestamp: now - 3600000, edited: false },
            { id: 'msg_2', conversationId: 'conv_1', authorId: 'user_1', content: 'Yes, see you there!', timestamp: now - 3500000, edited: false },
            { id: 'msg_3', conversationId: 'conv_1', authorId: 'user_2', content: 'Great, I\'ll bring the wine', timestamp: now - 3400000, edited: false },
        ]);
        this._messages.set('conv_2', [
            { id: 'msg_4', conversationId: 'conv_2', authorId: 'user_3', content: 'Meeting moved to 3pm', timestamp: now - 7200000, edited: false },
            { id: 'msg_5', conversationId: 'conv_2', authorId: 'user_1', content: 'Got it, thanks', timestamp: now - 7100000, edited: false },
        ]);
        this._messages.set('conv_3', [
            { id: 'msg_6', conversationId: 'conv_3', authorId: 'user_4', content: 'Welcome to the channel!', timestamp: now - 86400000, edited: false },
            { id: 'msg_7', conversationId: 'conv_3', authorId: 'user_5', content: 'Thanks! Excited to be here', timestamp: now - 86300000, edited: false },
        ]);
        this._messages.set('conv_4', [
            { id: 'msg_8', conversationId: 'conv_4', authorId: 'user_1', content: 'Hey team, quick update', timestamp: now - 1800000, edited: false },
        ]);
    }

    // RENAMED: getMessages -> fetchMessages
    fetchMessages(conversationId) {
        return this._messages.get(conversationId) || [];
    }

    // RENAMED: getMessage -> findMessage
    findMessage(messageId) {
        for (const msgs of this._messages.values()) {
            const msg = msgs.find(m => m.id === messageId);
            if (msg) return msg;
        }
        return null;
    }

    // RENAMED: addMessage -> insertMessage
    insertMessage(conversationId, message) {
        if (!this._messages.has(conversationId)) {
            this._messages.set(conversationId, []);
        }
        this._messages.get(conversationId).push(message);
        this._notify();
        return message;
    }

    editMessage(messageId, newContent) {
        for (const msgs of this._messages.values()) {
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
        for (const [convId, msgs] of this._messages.entries()) {
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
        this._listeners.add(listener);
        return () => this._listeners.delete(listener);
    }

    _notify() {
        for (const listener of this._listeners) {
            listener(this._messages);
        }
    }
}

// Channel Store (v2: renamed methods)
class ChannelStore {
    constructor() {
        this._channels = new Map();
        this._listeners = new Set();
        this._initializeDemoData();
    }

    _initializeDemoData() {
        const now = Date.now();
        this._channels.set('conv_1', {
            id: 'conv_1', type: 1, name: null, participants: ['user_1', 'user_2'],
            lastMessageAt: now - 3400000, unreadCount: 0,
        });
        this._channels.set('conv_2', {
            id: 'conv_2', type: 1, name: null, participants: ['user_1', 'user_3'],
            lastMessageAt: now - 7100000, unreadCount: 2,
        });
        this._channels.set('conv_3', {
            id: 'conv_3', type: 0, name: 'general', participants: ['user_1', 'user_4', 'user_5', 'user_6'],
            lastMessageAt: now - 86300000, unreadCount: 5,
        });
        this._channels.set('conv_4', {
            id: 'conv_4', type: 2, name: 'team-updates', participants: ['user_1', 'user_2', 'user_3', 'user_7'],
            lastMessageAt: now - 1800000, unreadCount: 1,
        });
    }

    // RENAMED: getChannel -> findChannel
    findChannel(id) {
        return this._channels.get(id) || null;
    }

    // RENAMED: getAllChannels -> listChannels
    listChannels() {
        return Array.from(this._channels.values());
    }

    // RENAMED: getDMFromUserId -> findDMByUser
    findDMByUser(userId) {
        for (const ch of this._channels.values()) {
            if (ch.type === 1 && ch.participants.includes(userId)) {
                return ch;
            }
        }
        return null;
    }

    createChannel(data) {
        const id = 'conv_' + Date.now();
        const channel = { id, ...data, lastMessageAt: Date.now(), unreadCount: 0 };
        this._channels.set(id, channel);
        this._notify();
        return channel;
    }

    updateChannel(id, data) {
        const ch = this._channels.get(id);
        if (ch) {
            Object.assign(ch, data);
            this._notify();
            return ch;
        }
        return null;
    }

    subscribe(listener) {
        this._listeners.add(listener);
        return () => this._listeners.delete(listener);
    }

    _notify() {
        for (const listener of this._listeners) {
            listener(this._channels);
        }
    }
}

// Current User Store (unchanged)
class CurrentUserStore {
    constructor() {
        this._currentUser = {
            id: 'user_1',
            username: 'alex_dev',
            global_name: 'Alex Developer',
            avatar: null,
            email: 'alex@example.com',
        };
        this._listeners = new Set();
    }

    getCurrentUser() {
        return this._currentUser;
    }

    setCurrentUser(user) {
        this._currentUser = user;
        this._notify();
    }

    subscribe(listener) {
        this._listeners.add(listener);
        return () => this._listeners.delete(listener);
    }

    _notify() {
        for (const listener of this._listeners) {
            listener(this._currentUser);
        }
    }
}

// Connection Store (unchanged)
class ConnectionStore {
    constructor() {
        this._state = 'connected';
        this._listeners = new Set();
        setInterval(() => {
            if (Math.random() < 0.01) {
                this._state = 'connecting';
                this._notify();
                setTimeout(() => {
                    this._state = 'connected';
                    this._notify();
                }, 1000);
            }
        }, 30000);
    }

    isConnected() {
        return this._state === 'connected';
    }

    getState() {
        return this._state;
    }

    addChangeListener(listener) {
        this._listeners.add(listener);
        return () => this._listeners.delete(listener);
    }

    removeChangeListener(listener) {
        this._listeners.delete(listener);
    }

    _notify() {
        for (const listener of this._listeners) {
            listener(this._state);
        }
    }
}

// WebSocket Manager (unchanged)
class WebSocketManager {
    constructor() {
        this._handlers = new Map();
        this._connected = false;
        this._simulateConnection();
    }

    _simulateConnection() {
        this._connected = true;
        setInterval(() => {
            if (this._connected && Math.random() < 0.3) {
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

        const handler = this._handlers.get('MESSAGE_CREATE');
        if (handler) handler(msg);
    }

    on(event, handler) {
        this._handlers.set(event, handler);
    }

    off(event) {
        this._handlers.delete(event);
    }

    send(data) {
        console.log('[WS] Sending:', data);
        return Promise.resolve({ success: true });
    }
}

// Export stores - RENAMED EXPORTS (simulating webpack module ID change + export rename)
const messageStore = new MessageStore();
const channelStore = new ChannelStore();
const currentUserStore = new CurrentUserStore();
const connectionStore = new ConnectionStore();
const wsManager = new WebSocketManager();

// Simulate webpack module registration with DIFFERENT chunk name and DIFFERENT exports
window.webpackChunktestbed_app_v2 = window.webpackChunktestbed_app_v2 || [];
window.webpackChunktestbed_app_v2.push([
    ['stores_v2'],
    {},
    (require) => {
        require.d(require, {
            // RENAMED EXPORTS - shape changed!
            getMessageRepository: () => messageStore,
            getChannelRepository: () => channelStore,
            getCurrentUserRepository: () => currentUserStore,
            getConnectionRepository: () => connectionStore,
            getWebSocketClient: () => wsManager,
        });
    },
]);

// Also expose on window with different names
window.TestbedStoresV2 = {
    messageRepository: messageStore,
    channelRepository: channelStore,
    currentUserRepository: currentUserStore,
    connectionRepository: connectionStore,
    wsClient: wsManager,
};

// Internal API functions (same as before - internal-http should still work)
window.TestbedAPI = {
    async getConversations() {
        const channels = channelStore.listChannels(); // RENAMED
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
        let msgs = messageStore.fetchMessages(conversationId); // RENAMED
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
        messageStore.insertMessage(conversationId, message); // RENAMED

        const ch = channelStore.findChannel(conversationId); // RENAMED
        if (ch) {
            ch.lastMessageAt = message.timestamp;
            channelStore.updateChannel(conversationId, { lastMessageAt: message.timestamp });
        }

        return message;
    },

    async markAsRead(conversationId) {
        const ch = channelStore.findChannel(conversationId);
        if (ch) {
            ch.unreadCount = 0;
            channelStore.updateChannel(conversationId, { unreadCount: 0 });
        }
        return { success: true },
    };
};

export { messageStore, channelStore, currentUserStore, connectionStore, wsManager };
// v3: Moved API endpoints (REST -> GraphQL-like internal calls)

class MessageStore {
    constructor() {
        this._messages = new Map();
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

    getMessages(conversationId) { return this._messages.get(conversationId) || []; }
    getMessage(messageId) {
        for (const msgs of this._messages.values()) {
            const msg = msgs.find(m => m.id === messageId);
            if (msg) return msg;
        }
        return null;
    }
    addMessage(conversationId, message) {
        if (!this._messages.has(conversationId)) this._messages.set(conversationId, []);
        this._messages.get(conversationId).push(message);
        this._notify();
        return message;
    }
    editMessage(messageId, newContent) {
        for (const msgs of this._messages.values()) {
            const msg = msgs.find(m => m.id === messageId);
            if (msg) { msg.content = newContent; msg.edited = true; msg.editedAt = Date.now(); this._notify(); return msg; }
        }
        return null;
    }
    deleteMessage(messageId) {
        for (const [_, msgs] of this._messages.entries()) {
            const idx = msgs.findIndex(m => m.id === messageId);
            if (idx !== -1) { msgs.splice(idx, 1); this._notify(); return true; }
        }
        return false;
    }
    subscribe(listener) { this._listeners.add(listener); return () => this._listeners.delete(listener); }
    _notify() { for (const l of this._listeners) l(this._messages); }
}

class ChannelStore {
    constructor() {
        this._channels = new Map(); this._listeners = new Set(); this._initializeDemoData();
    }
    _initializeDemoData() {
        const now = Date.now();
        this._channels.set('conv_1', { id: 'conv_1', type: 1, name: null, participants: ['user_1', 'user_2'], lastMessageAt: now - 3400000, unreadCount: 0 });
        this._channels.set('conv_2', { id: 'conv_2', type: 1, name: null, participants: ['user_1', 'user_3'], lastMessageAt: now - 7100000, unreadCount: 2 });
        this._channels.set('conv_3', { id: 'conv_3', type: 0, name: 'general', participants: ['user_1', 'user_4', 'user_5', 'user_6'], lastMessageAt: now - 86300000, unreadCount: 5 });
        this._channels.set('conv_4', { id: 'conv_4', type: 2, name: 'team-updates', participants: ['user_1', 'user_2', 'user_3', 'user_7'], lastMessageAt: now - 1800000, unreadCount: 1 });
    }
    getChannel(id) { return this._channels.get(id) || null; }
    getAllChannels() { return Array.from(this._channels.values()); }
    getDMFromUserId(userId) { for (const ch of this._channels.values()) if (ch.type === 1 && ch.participants.includes(userId)) return ch; return null; }
    createChannel(data) { const id = 'conv_' + Date.now(); const ch = { id, ...data, lastMessageAt: Date.now(), unreadCount: 0 }; this._channels.set(id, ch); this._notify(); return ch; }
    updateChannel(id, data) { const ch = this._channels.get(id); if (ch) { Object.assign(ch, data); this._notify(); return ch; } return null; }
    subscribe(listener) { this._listeners.add(listener); return () => this._listeners.delete(listener); }
    _notify() { for (const l of this._listeners) l(this._channels); }
}

class CurrentUserStore {
    constructor() { this._currentUser = { id: 'user_1', username: 'alex_dev', global_name: 'Alex Developer', avatar: null, email: 'alex@example.com' }; this._listeners = new Set(); }
    getCurrentUser() { return this._currentUser; }
    setCurrentUser(u) { this._currentUser = u; this._notify(); }
    subscribe(l) { this._listeners.add(l); return () => this._listeners.delete(l); }
    _notify() { for (const l of this._listeners) l(this._currentUser); }
}

class ConnectionStore {
    constructor() { this._state = 'connected'; this._listeners = new Set(); setInterval(() => { if (Math.random() < 0.01) { this._state = 'connecting'; this._notify(); setTimeout(() => { this._state = 'connected'; this._notify(); }, 1000); } }, 30000); }
    isConnected() { return this._state === 'connected'; }
    getState() { return this._state; }
    addChangeListener(l) { this._listeners.add(l); return () => this._listeners.delete(l); }
    removeChangeListener(l) { this._listeners.delete(l); }
    _notify() { for (const l of this._listeners) l(this._state); }
}

class WebSocketManager {
    constructor() { this._handlers = new Map(); this._connected = false; this._simulateConnection(); }
    _simulateConnection() { this._connected = true; setInterval(() => { if (this._connected && Math.random() < 0.3) this._simulateIncomingMessage(); }, 15000); }
    _simulateIncomingMessage() { const cs = ['conv_1','conv_2','conv_3','conv_4']; const cid = cs[Math.floor(Math.random()*cs.length)]; const as = ['user_2','user_3','user_4','user_5']; const aid = as[Math.floor(Math.random()*as.length)]; const msgs = ['Hey, quick question','Did you see the update?','Let me check on that','Sounds good to me',"I'll get back to you"]; const c = msgs[Math.floor(Math.random()*msgs.length)]; const msg = { t: 'MESSAGE_CREATE', d: { id: 'msg_'+Date.now(), conversationId: cid, authorId: aid, content: c, timestamp: new Date().toISOString(), edited: false } }; const h = this._handlers.get('MESSAGE_CREATE'); if (h) h(msg); }
    on(e, h) { this._handlers.set(e, h); }
    off(e) { this._handlers.delete(e); }
    send(d) { console.log('[WS] Sending:', d); return Promise.resolve({ success: true }); }
}

const messageStore = new MessageStore();
const channelStore = new ChannelStore();
const currentUserStore = new CurrentUserStore();
const connectionStore = new ConnectionStore();
const wsManager = new WebSocketManager();

// Webpack registration - SAME export names, DIFFERENT chunk global
window.webpackChunktestbed_app_v3 = window.webpackChunktestbed_app_v3 || [];
window.webpackChunktestbed_app_v3.push([
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

window.TestbedStores = { messageStore, channelStore, currentUserStore, connectionStore, wsManager };

// v3: MOVED ENDPOINTS - now uses /graphql endpoint with operations
window.TestbedAPI = {
    // GraphQL-style internal calls
    async _graphql(query, variables = {}) {
        const res = await fetch('/graphql', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ query, variables }),
        });
        return res.json();
    },

    async getConversations() {
        const data = await this._graphql(`
            query GetConversations {
                conversations { id type name participants lastMessageAt unreadCount }
            }
        `);
        return data.data?.conversations || channelStore.getAllChannels();
    },

    async getMessages(conversationId, params = {}) {
        const data = await this._graphql(`
            query GetMessages($conversationId: ID!, $limit: Int, $before: ID) {
                messages(conversationId: $conversationId, limit: $limit, before: $before) { id conversationId authorId content timestamp edited }
            }
        `, { conversationId, limit: params.limit || 50, before: params.before });
        return data.data?.messages || messageStore.getMessages(conversationId).slice(-(params.limit || 50));
    },

    async sendMessage(conversationId, content) {
        const user = currentUserStore.getCurrentUser();
        const data = await this._graphql(`
            mutation SendMessage($conversationId: ID!, $content: String!) {
                sendMessage(conversationId: $conversationId, content: $content) { id conversationId authorId content timestamp edited }
            }
        `, { conversationId, content });
        const msg = data.data?.sendMessage || { id: 'msg_' + Date.now(), conversationId, authorId: user.id, content, timestamp: Date.now(), edited: false };
        messageStore.addMessage(conversationId, msg);
        const ch = channelStore.getChannel(conversationId);
        if (ch) { ch.lastMessageAt = msg.timestamp; channelStore.updateChannel(conversationId, { lastMessageAt: msg.timestamp }); }
        return msg;
    },

    async markAsRead(conversationId) {
        await this._graphql(`mutation MarkAsRead($id: ID!) { markAsRead(id: $id) { success } }`, { id: conversationId });
        const ch = channelStore.getChannel(conversationId); if (ch) { ch.unreadCount = 0; channelStore.updateChannel(conversationId, { unreadCount: 0 }); }
        return { success: true };
    },
};

export { messageStore, channelStore, currentUserStore, connectionStore, wsManager };
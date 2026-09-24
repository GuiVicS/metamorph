// Main application entry point
import { messageStore, channelStore, currentUserStore, connectionStore, wsManager } from './stores.js';

// State
let currentConversationId = null;
let currentTab = 'direct';

// DOM Elements
const conversationList = document.querySelector('[data-list-id="chat-messages"]');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const emptyState = document.getElementById('emptyState');
const chatView = document.getElementById('chatView');
const chatTitle = document.getElementById('chatTitle');
const tabs = document.querySelectorAll('[data-testid="tab"]');
const searchInput = document.querySelector('[data-testid="search-input"]');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    renderConversationList();
    setupEventListeners();
    setupWebSocket();
    setupStoreListeners();
});

function setupEventListeners() {
    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            renderConversationList();
        });
    });

    // Conversation selection (delegated)
    conversationList.addEventListener('click', (e) => {
        const item = e.target.closest('[data-conversation-id]');
        if (item) {
            selectConversation(item.dataset.conversationId);
        }
    });

    // Send message
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
    });

    // Search
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        document.querySelectorAll('[data-conversation-id]').forEach(item => {
            const name = item.querySelector('.convo-name').textContent.toLowerCase();
            const preview = item.querySelector('.convo-preview').textContent.toLowerCase();
            item.style.display = name.includes(query) || preview.includes(query) ? '' : 'none';
        });
    });
}

function setupWebSocket() {
    wsManager.on('MESSAGE_CREATE', (msg) => {
        const data = msg.d;
        messageStore.addMessage(data.conversationId, data);

        // Update channel unread count if not current
        if (data.conversationId !== currentConversationId) {
            const ch = channelStore.getChannel(data.conversationId);
            if (ch) {
                ch.unreadCount = (ch.unreadCount || 0) + 1;
                channelStore.updateChannel(data.conversationId, { unreadCount: ch.unreadCount });
                renderConversationList();
            }
        } else {
            renderMessages();
        }
    });
}

function setupStoreListeners() {
    messageStore.subscribe(() => {
        if (currentConversationId) renderMessages();
    });

    channelStore.subscribe(() => {
        renderConversationList();
    });

    connectionStore.addChangeListener((state) => {
        console.log('[Connection]', state);
        // Could update UI indicator here
    });
}

function renderConversationList() {
    const channels = channelStore.getAllChannels()
        .filter(c => {
            if (currentTab === 'direct') return c.type === 1;
            if (currentTab === 'groups') return c.type === 2;
            if (currentTab === 'channels') return c.type === 0;
            return true;
        })
        .sort((a, b) => b.lastMessageAt - a.lastMessageAt);

    const currentUser = currentUserStore.getCurrentUser();

    conversationList.innerHTML = channels.map(ch => {
        const otherParticipant = ch.participants.find(p => p !== currentUser.id);
        const otherUser = getUserInfo(otherParticipant);
        const lastMsg = messageStore.getMessages(ch.id).slice(-1)[0];
        const isActive = ch.id === currentConversationId;

        return `
            <div class="conversation-item ${isActive ? 'active : ''}" data-conversation-id="${ch.id}" data-testid="conversation-item">
                <div class="convo-header">
                    <span class="convo-name">${ch.name || otherUser.name}</span>
                    <span class="convo-time">${formatTime(ch.lastMessageAt)}</span>
                </div>
                <div class="convo-preview">${lastMsg ? lastMsg.content : 'No messages yet'}</div>
                ${ch.unreadCount ? `<span class="convo-unread">${ch.unreadCount}</span>` : ''}
            </div>
        `;
    }).join('');
}

function selectConversation(conversationId) {
    currentConversationId = conversationId;
    const ch = channelStore.getChannel(conversationId);
    const currentUser = currentUserStore.getCurrentUser();
    const otherParticipant = ch.participants.find(p => p !== currentUser.id);
    const otherUser = getUserInfo(otherParticipant);

    emptyState.style.display = 'none';
    chatView.style.display = 'flex';
    chatTitle.textContent = ch.name || otherUser.name;

    // Update active state
    document.querySelectorAll('[data-conversation-id]').forEach(item => {
        item.classList.toggle('active', item.dataset.conversationId === conversationId);
    });

    // Mark as read
    if (ch.unreadCount) {
        window.TestbedAPI.markAsRead(conversationId);
    }

    renderMessages();
    messageInput.focus();
}

function renderMessages() {
    if (!currentConversationId) return;

    const msgs = messageStore.getMessages(currentConversationId);
    const currentUser = currentUserStore.getCurrentUser();

    messagesContainer.innerHTML = msgs.map(msg => {
        const isOutbound = msg.authorId === currentUser.id;
        const sender = getUserInfo(msg.authorId);

        return `
            <div class="message ${isOutbound ? 'outbound' : 'inbound'}" data-message-id="${msg.id}">
                <div class="message-header">
                    <span class="message-sender">${isOutbound ? 'You' : sender.name}</span>
                    <span class="message-time">${formatTime(msg.timestamp)}</span>
                    ${msg.edited ? '<span class="message-time">(edited)</span>' : ''}
                </div>
                <div class="message-text">${escapeHtml(msg.content)}</div>
            </div>
        `;
    }).join('');

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || !currentConversationId) return;

    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendBtn.disabled = true;

    try {
        await window.TestbedAPI.sendMessage(currentConversationId, content);
    } catch (err) {
        console.error('Send failed:', err);
        showToast('Failed to send message');
    } finally {
        sendBtn.disabled = false;
    }
}

function getUserInfo(userId) {
    const users = {
        user_1: { id: 'user_1', name: 'You', username: 'alex_dev' },
        user_2: { id: 'user_2', name: 'Sarah Chen', username: 'sarah_c' },
        user_3: { id: 'user_3', name: 'Mike Johnson', username: 'mike_j' },
        user_4: { id: 'user_4', name: 'Emma Wilson', username: 'emma_w' },
        user_5: { id: 'user_5', name: 'David Park', username: 'david_p' },
        user_6: { id: 'user_6', name: 'Lisa Brown', username: 'lisa_b' },
        user_7: { id: 'user_7', name: 'James Miller', username: 'james_m' },
    };
    return users[userId] || { id: userId, name: userId, username: userId };
}

function formatTime(ts) {
    const date = new Date(ts);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h';
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd';
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Expose for debugging
window.TestbedApp = {
    selectConversation,
    sendMessage,
    get messageStore() { return messageStore; },
    get channelStore() { return channelStore; },
};
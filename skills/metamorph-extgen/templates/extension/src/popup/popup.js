/**
 * Popup Script - Extension UI
 */

document.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  setInterval(loadStatus, 5000);
});

async function loadStatus() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'getStatus' });
    if (response.success) {
      renderStatus(response.result);
    }
  } catch (err) {
    console.error('[Popup] Status load failed:', err);
  }
}

function renderStatus(status) {
  const statusEl = document.getElementById('statusEl');
  const statusText = document.getElementById('statusText');
  const fingerprintInfo = document.getElementById('fingerprintInfo');
  const capabilitiesList = document.getElementById('capabilitiesList');

  // Connection status
  if (status.connected) {
    statusEl.className = 'status connected';
    statusText.textContent = 'Connected';
  } else {
    statusEl.className = 'status disconnected';
    statusText.textContent = 'Disconnected';
  }

  // Fingerprint info
  if (status.fingerprint) {
    fingerprintInfo.textContent = `${status.fingerprint.platform} • v${status.fingerprint.version}`;
  } else {
    fingerprintInfo.textContent = 'No fingerprint loaded';
  }

  // Capabilities
  if (status.capabilities && status.capabilities.length > 0) {
    capabilitiesList.innerHTML = status.capabilities.map(cap => `
      <div class="capability">
        <span class="cap-name">${cap}</span>
        <span class="cap-status ok">Ready</span>
      </div>
    `).join('');
  } else {
    capabilitiesList.innerHTML = '<div style="color: #999; font-size: 12px; text-align: center; padding: 20px;">No capabilities available</div>';
  }
}
// AutoGEO Cookie Sync - Popup Script
const PLATFORMS = ['doubao', 'deepseek', 'qianwen'];
let syncInProgress = false;

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  restoreButtonStates();
  bindEvents();
  logStatus('扩展已就绪，请登录平台后点击同步');
});

function bindEvents() {
  document.querySelectorAll('.sync-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (syncInProgress) return;
      syncPlatform(btn.dataset.platform);
    });
  });

  document.getElementById('backendUrl').addEventListener('change', (e) => {
    chrome.storage.local.set({ backendUrl: e.target.value.trim() });
  });

  document.getElementById('openApp').addEventListener('click', async (e) => {
    e.preventDefault();
    const backendUrl = (await chrome.storage.local.get(['backendUrl'])).backendUrl || 'http://127.0.0.1:8001';
    chrome.tabs.create({ url: backendUrl });
  });
}

function loadSettings() {
  chrome.storage.local.get(['backendUrl'], (result) => {
    if (result.backendUrl) {
      document.getElementById('backendUrl').value = result.backendUrl;
    }
  });
}

function restoreButtonStates() {
  chrome.storage.local.get(['syncStates'], (result) => {
    const states = result.syncStates || {};
    for (const platform of PLATFORMS) {
      const state = states[platform];
      if (state) updateButton(platform, state.status, state.cookieCount);
    }
  });
}

function updateButton(platform, status, cookieCount) {
  const btn = document.getElementById(`btn-${platform}`);
  const statusEl = document.getElementById(`status-${platform}`);
  btn.className = 'sync-btn ' + status;
  switch (status) {
    case 'syncing': btn.textContent = '同步中...'; btn.disabled = true; break;
    case 'done': btn.textContent = `✓ ${cookieCount || ''}个`; btn.disabled = false; statusEl.textContent = '已同步'; break;
    case 'error': btn.textContent = '重试'; btn.disabled = false; statusEl.textContent = '同步失败'; break;
    default: btn.textContent = '同步'; btn.disabled = false;
  }
  saveButtonState(platform, status, cookieCount);
}

function saveButtonState(platform, status, cookieCount) {
  chrome.storage.local.get(['syncStates'], (result) => {
    const states = result.syncStates || {};
    states[platform] = { status, cookieCount, time: Date.now() };
    chrome.storage.local.set({ syncStates: states });
  });
}

function logStatus(msg, type) {
  const el = document.getElementById('result');
  el.textContent = msg;
  el.className = 'result-msg ' + (type || '');
  if (msg) setTimeout(() => { el.className = 'result-msg'; el.textContent = ''; }, 5000);
}

async function syncPlatform(platform) {
  syncInProgress = true;
  updateButton(platform, 'syncing');
  logStatus(`正在获取 ${platform} 的 Cookie...`, '');

  try {
    logStatus(`Step 1/3: 查找 ${platform} 的 Cookie...`, '');
    const response = await chrome.runtime.sendMessage({
      action: 'syncCookies',
      platform: platform,
      localStorage: {},
    });

    if (!response) {
      updateButton(platform, 'error');
      logStatus('扩展 Service Worker 无响应，请刷新扩展（chrome://extensions/ → 刷新按钮）', 'error');
      return;
    }

    if (response.success) {
      updateButton(platform, 'done', response.cookie_count || '?');
      logStatus(`${platform} 同步成功！${response.cookie_count || 0} 个 cookie 已传至后端`, 'success');
    } else {
      updateButton(platform, 'error');
      logStatus(`${platform}: ${response.error || '同步失败'}`, 'error');
    }
  } catch (e) {
    updateButton(platform, 'error');
    logStatus(`通信失败: ${e.message}。请检查后端是否运行，扩展是否已刷新。`, 'error');
  } finally {
    syncInProgress = false;
  }
}

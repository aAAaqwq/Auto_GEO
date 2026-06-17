// AutoGEO Cookie Sync - Content Script
// 精简版：自动同步由 background.js 的 chrome.cookies.onChanged 负责
// 这里只放一个手动按钮兜底

(function () {
  'use strict';

  function detectPlatform() {
    const host = location.hostname;
    if (host.includes('doubao.com')) return 'doubao';
    if (host.includes('deepseek.com')) return 'deepseek';
    if (host.includes('qianwen.com') || host.includes('tongyi.aliyun.com')) return 'qianwen';
    return null;
  }

  function readLocalStorage() {
    const data = {};
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        data[key] = localStorage.getItem(key);
      }
    } catch (e) {}
    return data;
  }

  function injectButton(platform) {
    if (document.getElementById('autogeo-btn')) return;

    const btn = document.createElement('div');
    btn.id = 'autogeo-btn';
    btn.title = 'AutoGEO: 手动同步 Cookie';
    btn.style.cssText =
      'position:fixed;bottom:20px;right:20px;z-index:99998;' +
      'width:28px;height:28px;border-radius:50%;' +
      'background:#0066FF;color:#fff;display:flex;align-items:center;justify-content:center;' +
      'cursor:pointer;font-size:12px;font-weight:bold;opacity:0.5;' +
      'box-shadow:0 2px 6px rgba(0,0,0,0.2);transition:opacity 0.3s;';
    btn.textContent = 'A';

    btn.addEventListener('mouseenter', () => { btn.style.opacity = '1'; });
    btn.addEventListener('mouseleave', () => { btn.style.opacity = '0.5'; });

    btn.addEventListener('click', async () => {
      btn.textContent = '⏳'; btn.style.opacity = '1';
      try {
        const result = await chrome.runtime.sendMessage({
          action: 'syncCookies',
          platform: platform,
          localStorage: readLocalStorage(),
        });
        btn.textContent = (result && result.success) ? '✓' : '✗';
      } catch (e) {
        btn.textContent = '✗';
      }
      setTimeout(() => { btn.textContent = 'A'; btn.style.opacity = '0.5'; }, 2000);
    });

    document.body.appendChild(btn);
  }

  function init() {
    const platform = detectPlatform();
    if (!platform) return;

    if (document.body) {
      injectButton(platform);
    } else {
      const obs = new MutationObserver(() => {
        if (document.body) { obs.disconnect(); injectButton(platform); }
      });
      obs.observe(document.documentElement, { childList: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

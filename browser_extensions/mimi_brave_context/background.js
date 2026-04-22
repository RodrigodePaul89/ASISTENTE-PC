const ENDPOINT = 'http://127.0.0.1:37655/context';
let lastSentSignature = '';

async function postContext(payload) {
  try {
    await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (_error) {
    // Silencioso: si Mimi no esta abierta, no molestamos al usuario.
  }
}

function normalizeTitle(rawTitle) {
  const title = String(rawTitle || '').trim();
  if (!title) {
    return '';
  }

  const browserSuffixes = [' - Brave', ' - Google Chrome', ' - Microsoft Edge', ' - Mozilla Firefox'];
  for (const suffix of browserSuffixes) {
    if (title.endsWith(suffix)) {
      return title.slice(0, -suffix.length).trim();
    }
  }
  return title;
}

async function sendActiveTabContext() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs || !tabs.length) {
    return;
  }

  const tab = tabs[0];
  const payload = {
    browser: 'brave',
    title: normalizeTitle(tab.title || ''),
    url: String(tab.url || '').trim(),
    tabId: Number(tab.id || 0),
    timestamp: Math.floor(Date.now() / 1000),
  };

  const signature = `${payload.title}::${payload.url}`;
  if (signature && signature === lastSentSignature) {
    return;
  }

  lastSentSignature = signature;
  await postContext(payload);
}

chrome.tabs.onActivated.addListener(() => {
  sendActiveTabContext();
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (!tab || !tab.active) {
    return;
  }
  if (changeInfo.status === 'complete' || typeof changeInfo.title === 'string' || typeof changeInfo.url === 'string') {
    sendActiveTabContext();
  }
});

chrome.windows.onFocusChanged.addListener(() => {
  sendActiveTabContext();
});

chrome.runtime.onStartup.addListener(() => {
  sendActiveTabContext();
});

chrome.runtime.onInstalled.addListener(() => {
  sendActiveTabContext();
});

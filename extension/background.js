let nativePort = null;

// تسجيل وقت فتح المتصفح مرة واحدة فقط في الجلسة
chrome.runtime.onStartup.addListener(() => {
    chrome.storage.session.set({ startupTime: Date.now() });
});

function getNativePort() {
    if (nativePort) return nativePort;

    console.log("Connecting to native host...");
    nativePort = chrome.runtime.connectNative('com.python.download.manager');

    nativePort.onMessage.addListener((message) => {
        console.log("Received from Python:", message);
    });

    nativePort.onDisconnect.addListener(() => {
        if (chrome.runtime.lastError) {
            console.error("Native Host Error:", chrome.runtime.lastError.message);
        }
        nativePort = null;
    });

    return nativePort;
}

chrome.downloads.onCreated.addListener(async (downloadItem) => {
    const { startupTime } = await chrome.storage.session.get("startupTime");
    if (startupTime && (Date.now() - startupTime < 8000)) return;

    const targetUrl = downloadItem.finalUrl || downloadItem.url;
    if (!targetUrl || targetUrl.startsWith("blob:") || targetUrl.startsWith("data:")) return;

    const downloadStartTime = new Date(downloadItem.startTime).getTime();
    if (Date.now() - downloadStartTime > 3000) return;

    // إلغاء تحميل المتصفح فوراً
    chrome.downloads.cancel(downloadItem.id, () => {
        if (chrome.runtime.lastError) return;
        chrome.downloads.erase({ id: downloadItem.id });
    });

    sendUrlToDownloader(targetUrl);
});

function sendUrlToDownloader(downloadUrl) {
  chrome.runtime.sendNativeMessage(
    "com.python.download.manager",
    { url: downloadUrl },
    (response) => {
      if (chrome.runtime.lastError) {
        console.warn("Bridge notice:", chrome.runtime.lastError.message);
        return;
      }
      console.log("Downloader response:", response);
    }
  );
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "download_video" && request.url) {
        sendUrlToDownloader(request.url);
        sendResponse({ status: "success" });
    }
    return true;
});
let isInitialStartup = true;
let nativePort = null;

// Wait 8 seconds to bypass startup or restored downloads
setTimeout(() => {
    isInitialStartup = false;
    console.log("Startup period over. Intercepted active user downloads.");
}, 8000);

// Helper function to get or create an active native port
function getNativePort() {
    if (nativePort) {
        return nativePort;
    }

    console.log("Establishing a new stable connection with Python bridge...");
    nativePort = chrome.runtime.connectNative('com.python.download.manager');

    nativePort.onMessage.addListener((message) => {
        console.log("Received from Python:", message);
    });

    nativePort.onDisconnect.addListener(() => {
        console.log("Python bridge disconnected cleanly.");
        nativePort = null; // Reset port so it can be recreated on the next download
    });

    return nativePort;
}

chrome.downloads.onCreated.addListener((downloadItem) => {
    if (isInitialStartup) return;

    const downloadStartTime = new Date(downloadItem.startTime).getTime();
    const now = Date.now();
    if (now - downloadStartTime > 3000) return;

    // إلغاء تحميل المتصفح فوراً وبدون تأخير لمنع التحميل المزدوج
    chrome.downloads.cancel(downloadItem.id, () => {
        if (chrome.runtime.lastError) {
            console.log("Download already handled or cancelled:", chrome.runtime.lastError.message);
        }
    });
    
    // إرسال الرابط للبايثون فوراً
    sendToPython(downloadItem.url);
    
    // مسح التحميل من قائمة المتصفح لعدم تشويه المظهر
    setTimeout(() => {
        chrome.downloads.erase({ id: downloadItem.id });
    }, 500);
});

function sendToPython(downloadUrl) {
    try {
        const port = getNativePort();
        if (port) {
            port.postMessage({ url: downloadUrl });
            console.log("URL sent successfully to production bridge:", downloadUrl);
        }
    } catch (error) {
        console.error("Critical communication error in production:", error);
        nativePort = null; // Ensure fresh retry next time
    }
}

// مستمع لاستقبال الرابط من الزرار المحقون وتمريره للبايثون عبر الـ Native Messaging الحالي
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "download_video" && request.url) {
        console.log("Sending URL to Python Bridge:", request.url);
        sendToPython(request.url);
        sendResponse({ status: "success" });
    }
    return true;
});
// دالة لحقن الأيقونة العائمة على يمين الشاشة
function injectPythonFloatingButton() {
    // التأكد من عدم تكرار إنشاء الأيقونة
    if (document.getElementById("python-yt-floating-btn")) return;

    // إنشاء زر التحميل الدائري
    const floatBtn = document.createElement("button");
    floatBtn.id = "python-yt-floating-btn";
    
    // إضافة أيقونة التنزيل داخل الدائرة (شكل سهم لأسفل احترافي)
    floatBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="26" height="26" fill="white" style="display: block;">
            <path d="M5 20h14v-2H5v2zm7-18L5.33 11h4V16h5.34v-5h4L12 2z"/>
        </svg>
    `;
    
    // تنسيق الأيقونة لتطفو بشكل ثابت وأنيق على اليمين (Floating CSS)
    floatBtn.style.cssText = `
        position: fixed;
        right: 25px;
        bottom: 40px;
        width: 55px;
        height: 55px;
        background-color: #2a54c8;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999999;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        transition: all 0.2s ease-in-out;
    `;

    // تلميح صغير يظهر عند الوقوف على الأيقونة بالماوس (Tooltip)
    floatBtn.title = "Download Video";

    // تأثيرات حركية خفيفة عند التفاعل بالماوس
    floatBtn.onmouseover = () => {
        floatBtn.style.backgroundColor = "#1a3eb3";
        floatBtn.style.transform = "scale(1.1)";
    };
    floatBtn.onmouseout = () => {
        floatBtn.style.backgroundColor = "#2a54c8";
        floatBtn.style.transform = "scale(1)";
    };
    floatBtn.onmousedown = () => {
        floatBtn.style.transform = "scale(0.9)";
    };

    // عند الضغط على الأيقونة الدائرية
    floatBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        const currentVideoUrl = window.location.href;
        
        // إرسال الرابط مباشرة لخلفية الإكستنشن
        chrome.runtime.sendMessage({ action: "download_video", url: currentVideoUrl });

        // تأثير بصري سريع للدائرة عند الضغط (تحول للون البرتقالي لتأكيد الأمر)
        floatBtn.style.backgroundColor = "#e67e22";
        setTimeout(() => {
            floatBtn.style.backgroundColor = "#2a54c8";
        }, 2000);
    });

    // حقن الأيقونة في جسم الصفحة مباشرة لضمان ثباتها
    document.body.appendChild(floatBtn);
}

// مراقبة الصفحة بشكل مستمر لكي تظهر الأيقونة فقط عندما تكون داخل صفحة فيديو يوتيوب
setInterval(() => {
    if (window.location.pathname === "/watch") {
        injectPythonFloatingButton();
        
        // إذا كانت الأيقونة مخفية لأي سبب، قم بإظهارها
        const btn = document.getElementById("python-yt-floating-btn");
        if (btn) btn.style.display = "flex";
    } else {
        // إخفاء الأيقونة تلقائياً إذا خرجت من صفحة الفيديو إلى الصفحة الرئيسية ليوتيوب مثلاً
        const btn = document.getElementById("python-yt-floating-btn");
        if (btn) btn.style.display = "none";
    }
}, 1000);
let idImageElement = null;
let selfieDataUrl = null;
let cameraStream = null;
let modelsLoaded = false;
let faceDetected = false;
let faceDetectionInterval = null;

async function goToStep2() {
    document.getElementById("step1").classList.add("hidden");
    document.getElementById("step2").classList.remove("hidden");

    document.getElementById("step2-indicator").classList.add("active");

    await Promise.all([
        startCamera(),
        loadModels()
    ]);
}

function goToStep3() {
    if (faceDetectionInterval) {
        clearInterval(faceDetectionInterval);
        faceDetectionInterval = null;
    }

    if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
    }

    document.getElementById("step2").classList.add("hidden");
    document.getElementById("step3").classList.remove("hidden");

    document.getElementById("step3-indicator").classList.add("active");
}

document.getElementById("id-upload")?.addEventListener("change", function (event) {
    const file = event.target.files[0];

    if (!file) return;

    const reader = new FileReader();

    reader.onload = function (ev) {
        const img = document.getElementById("id-img");
        img.src = ev.target.result;

        idImageElement = new Image();
        idImageElement.src = ev.target.result;

        document.getElementById("id-preview").classList.remove("hidden");
        document.getElementById("step1-next").disabled = false;
    };

    reader.readAsDataURL(file);
});

async function startCamera() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: "user",
            },
        });

        const video = document.getElementById("camera-video");
        video.srcObject = cameraStream;

        await new Promise((resolve) => {
            video.onloadedmetadata = () => {
                video.width = video.videoWidth;
                video.height = video.videoHeight;
                resolve();
            };
        });

        await video.play();

    } catch (error) {
        const status = document.getElementById("face-status");
        status.textContent = "لا يمكن الوصول إلى الكاميرا. تأكد من السماح بالوصول.";
        status.style.color = "#B42318";
    }
}

async function loadModels() {
    if (modelsLoaded) return;

    const MODEL_URL = window.location.origin + "/static/models";

    try {
        await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
            faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
        ]);

        modelsLoaded = true;

        document.getElementById("models-loading").classList.add("hidden");
        document.getElementById("camera-container").classList.remove("hidden");

        detectFaceLoop();

    } catch (error) {
        document.getElementById("models-loading").innerHTML =
            '<p style="color:#B42318;">خطأ في تحميل نماذج الذكاء الاصطناعي</p>';
    }
}

async function detectFaceLoop() {
    const video = document.getElementById("camera-video");
    const statusEl = document.getElementById("face-status");
    const captureBtn = document.getElementById("capture-btn");

    await new Promise((resolve) => {
        if (video.readyState >= 2) {
            resolve();
        } else {
            video.addEventListener("loadeddata", resolve, { once: true });
        }
    });

    if (faceDetectionInterval) {
        clearInterval(faceDetectionInterval);
    }

    faceDetectionInterval = setInterval(async () => {
        if (!modelsLoaded || video.paused || video.ended) return;
        if (!video.videoWidth || !video.videoHeight) return;
        if (video.readyState < 4) return;

        try {
            const detection = await faceapi.detectSingleFace(
                video,
                new faceapi.TinyFaceDetectorOptions({
                    inputSize: 224,
                    scoreThreshold: 0.3,
                })
            );

            if (detection) {
                faceDetected = true;
                statusEl.textContent = "تم الكشف عن وجهك — اضغط التقاط";
                statusEl.style.color = "#2F8F55";
                captureBtn.disabled = false;
            } else {
                faceDetected = false;
                statusEl.textContent = "ابحث عن وجهك في الكاميرا...";
                statusEl.style.color = "#6F7482";
                captureBtn.disabled = true;
            }
        } catch (error) {
            console.log(error);
        }
    }, 300);
}

function captureSelfie() {
    const video = document.getElementById("camera-video");

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    canvas.getContext("2d").drawImage(video, 0, 0);

    selfieDataUrl = canvas.toDataURL("image/jpeg", 0.9);

    document.getElementById("selfie-img").src = selfieDataUrl;
    document.getElementById("selfie-preview").classList.remove("hidden");
    document.getElementById("camera-container").classList.add("hidden");
    document.getElementById("compare-btn").disabled = false;
}

function retakeSelfie() {
    selfieDataUrl = null;

    document.getElementById("selfie-preview").classList.add("hidden");
    document.getElementById("camera-container").classList.remove("hidden");
    document.getElementById("compare-btn").disabled = true;
}

async function compareFaces() {
    const nextUrl = new URLSearchParams(window.location.search).get("next");

    goToStep3();

    try {
        const idDescriptor = await getFaceDescriptor(idImageElement);

        if (!idDescriptor) {
            showResult(false);
            return;
        }

        const selfieImg = new Image();
        selfieImg.src = selfieDataUrl;

        await selfieImg.decode();

        const selfieDescriptor = await getFaceDescriptor(selfieImg);

        if (!selfieDescriptor) {
            showResult(false);
            return;
        }

        const distance = faceapi.euclideanDistance(
            idDescriptor,
            selfieDescriptor
        );

        console.log("Face distance:", distance);

        if (distance < 0.6) {
            await notifyBackend();

            if (nextUrl) {
                window.location.href =
                    nextUrl + "?open_sign_modal=1";
                return;
            }

            showResult(true);
        } else {
            showResult(false);
        }

    } catch (error) {
        console.error("Comparison error:", error);
        showResult(false);
    }
}

async function getFaceDescriptor(imgElement) {
    const detection = await faceapi
        .detectSingleFace(
            imgElement,
            new faceapi.TinyFaceDetectorOptions({
                inputSize: 224,
                scoreThreshold: 0.3,
            })
        )
        .withFaceLandmarks()
        .withFaceDescriptor();

    return detection ? detection.descriptor : null;
}

async function notifyBackend() {
    const csrfToken =
        document.cookie
            .split(";")
            .map((cookie) => cookie.trim())
            .find((cookie) => cookie.startsWith("csrftoken="))
            ?.split("=")[1] || "";

    const response = await fetch("/accounts/verify-identity/confirm/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
        },
    });

    const data = await response.json();
    console.log("Backend response:", data);
}

function showResult(success) {
    document.getElementById("comparing-loading").classList.add("hidden");

    if (success) {
        document.getElementById("result-success").classList.remove("hidden");
    } else {
        document.getElementById("result-failure").classList.remove("hidden");
    }
}

window.addEventListener("unhandledrejection", function (event) {
    if (
        event.reason &&
        event.reason.message &&
        event.reason.message.includes("Box.constructor")
    ) {
        event.preventDefault();
    }
});

function resetVerification() {
    selfieDataUrl = null;
    idImageElement = null;

    if (faceDetectionInterval) {
        clearInterval(faceDetectionInterval);
        faceDetectionInterval = null;
    }

    document.getElementById("step3").classList.add("hidden");
    document.getElementById("step1").classList.remove("hidden");

    document.getElementById("id-preview").classList.add("hidden");
    document.getElementById("step1-next").disabled = true;

    document.getElementById("step2-indicator").classList.remove("active");
    document.getElementById("step3-indicator").classList.remove("active");

    if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
        cameraStream = null;
    }
}
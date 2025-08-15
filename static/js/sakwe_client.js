// static/js/sakwe_client.js

document.addEventListener('DOMContentLoaded', () => {
    const sakweButton = document.getElementById('sakwe-button');
    const sakweStatus = document.getElementById('sakwe-status');
    const audioFeaturesEnabled = {{ audio_features_enabled | tojson }};

    if (!audioFeaturesEnabled) {
        sakweButton.disabled = true;
        sakweStatus.textContent = 'Audio features disabled.';
        return;
    }

    let websocket;
    let mediaRecorder;
    let isRecording = false;
    let audioContext;
    let audioQueue = [];
    let isPlaying = false;

    sakweButton.addEventListener('click', () => {
        if (isRecording) {
            stopSakweGame();
        } else {
            startSakweGame();
        }
    });

    function startSakweGame() {
        sakweStatus.textContent = 'Connecting...';
        const wsUrl = `ws://${window.location.host}/ws/sakwe`;
        websocket = new WebSocket(wsUrl);
        audioContext = new (window.AudioContext || window.webkitAudioContext)();

        websocket.onopen = () => {
            sakweStatus.textContent = 'Connected. Start speaking!';
            sakweButton.textContent = 'Stop Sakwe Game';
            isRecording = true;
            startMicrophone();
        };

        websocket.onmessage = async (event) => {
            const audioData = await event.data.arrayBuffer();
            audioQueue.push(audioData);
            if (!isPlaying) {
                playNextInQueue();
            }
        };

        websocket.onclose = () => {
            sakweStatus.textContent = 'Disconnected.';
            sakweButton.textContent = 'Start Sakwe Game';
            isRecording = false;
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
        };

        websocket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            sakweStatus.textContent = 'Error connecting.';
            isRecording = false;
        };
    }

    function stopSakweGame() {
        if (websocket) {
            websocket.close();
        }
    }

    function startMicrophone() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
                        websocket.send(event.data);
                    }
                };

                mediaRecorder.start(500); // Send audio data every 500ms
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                sakweStatus.textContent = 'Could not access microphone.';
            });
    }

    async function playNextInQueue() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            return;
        }
        isPlaying = true;
        const audioData = audioQueue.shift();
        const audioBuffer = await audioContext.decodeAudioData(audioData);
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.onended = playNextInQueue;
        source.start();
    }
});

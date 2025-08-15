// static/js/sakwe_client.js

let websocket;
let mediaRecorder;
let isRecording = false;

const sakweButton = document.getElementById('sakwe-button');
const sakweStatus = document.getElementById('sakwe-status');

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

    websocket.onopen = () => {
        sakweStatus.textContent = 'Connected. Start speaking!';
        sakweButton.textContent = 'Stop Sakwe Game';
        isRecording = true;
        startMicrophone();
    };

    websocket.onmessage = (event) => {
        // This is an audio chunk from the server
        const audioChunk = event.data;
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createBufferSource();

        audioContext.decodeAudioData(audioChunk, (buffer) => {
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.start(0);
        });
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
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(event.data);
                }
            };

            mediaRecorder.start(250); // Send audio data every 250ms
        })
        .catch(error => {
            console.error('Error accessing microphone:', error);
            sakweStatus.textContent = 'Could not access microphone.';
        });
}

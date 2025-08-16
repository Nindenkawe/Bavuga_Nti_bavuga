// static/js/sakwe_client.js

document.addEventListener('DOMContentLoaded', () => {
    const recordButton = document.getElementById('record-button');
    const streamStatus = document.getElementById('stream-status');
    
    let websocket;
    let mediaRecorder;
    let isRecording = false;

    recordButton.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    function startRecording() {
        streamStatus.textContent = 'Connecting...';
        const wsUrl = `ws://${window.location.host}/ws/audio`;
        websocket = new WebSocket(wsUrl);

        websocket.onopen = () => {
            streamStatus.textContent = 'Connected. Start speaking!';
            recordButton.classList.remove('bg-green-500', 'hover:bg-green-700');
            recordButton.classList.add('bg-red-500', 'hover:bg-red-700');
            isRecording = true;
            startMicrophone();
        };

        websocket.onmessage = (event) => {
            // Handle transcription results from the server
            console.log("Received from server: ", event.data);
            const answerInput = document.getElementById('answer-input');
            answerInput.value = event.data;
            streamStatus.textContent = "Transcription: " + event.data;
        };

        websocket.onclose = () => {
            streamStatus.textContent = 'Disconnected.';
            recordButton.classList.remove('bg-red-500', 'hover:bg-red-700');
            recordButton.classList.add('bg-green-500', 'hover:bg-green-700');
            isRecording = false;
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
        };

        websocket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            streamStatus.textContent = 'Error connecting.';
            isRecording = false;
        };
    }

    function stopRecording() {
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

                mediaRecorder.start(1000); // Send audio data every 1 second
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                streamStatus.textContent = 'Could not access microphone.';
            });
    }
});
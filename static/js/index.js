function init(audioFeaturesEnabled, initialLives, initialScore, initialGameMode) {
    let currentChallengeId = null;
    let lives = initialLives;
    let score = initialScore;
    let gusakuzaState = 'done';
    let currentGameMode = initialGameMode;

    const answerInput = document.getElementById('answer-input');
    const submitBtn = document.getElementById('submit-btn');
    const newChallengeBtn = document.getElementById('new-challenge-btn');
    const instructionElement = document.getElementById('instruction');
    const challengeContent = document.getElementById('challenge-content');
    const feedbackMessage = document.getElementById('feedback-message');
    const correctAnswerFeedback = document.getElementById('correct-answer-feedback');
    const sourceTextElement = document.getElementById('source-text');
    const contextTextElement = document.getElementById('context-text');
    const somaBtn = document.getElementById('soma-btn');
    const micBtn = document.getElementById('mic-btn');
    const audioPlayer = document.getElementById('audio-player');
    const gameModeSelector = document.getElementById('game-mode-select');
    const hintBtn = document.getElementById('hint-btn');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    updateScoreboard();
    gameModeSelector.value = currentGameMode;
    getNewChallenge();
    if (!audioFeaturesEnabled) {
        micBtn.disabled = true;
        micBtn.style.cursor = 'not-allowed';
        micBtn.style.opacity = '0.5';
    }

    gameModeSelector.addEventListener('change', () => {
        currentGameMode = gameModeSelector.value;
        getNewChallenge();
    });

    submitBtn.addEventListener('click', submitAnswer);
    newChallengeBtn.addEventListener('click', getNewChallenge);
    somaBtn.addEventListener('click', handleSoma);
    micBtn.addEventListener('click', toggleRecording);
    hintBtn.addEventListener('click', getHint);

    async function handleSoma() {
        if (gusakuzaState !== 'intro') return;
        try {
            const data = await fetchApi('/soma', { method: 'POST' });
            gusakuzaState = 'riddle';
            currentChallengeId = data.challenge_id;
            sourceTextElement.textContent = data.source_text;
            instructionElement.textContent = "Soma!";
            somaBtn.classList.add('hidden');
            answerInput.classList.remove('hidden');
            submitBtn.parentElement.classList.remove('hidden');
            hintBtn.classList.remove('hidden');
        } catch (error) {
            instructionElement.textContent = 'Failed to get riddle. Try again.';
            console.error("Error during 'soma':", error);
        }
    }

    function updateScoreboard() {
        document.getElementById('lives-count').textContent = '♥'.repeat(lives);
        document.getElementById('current-score').textContent = score;
    }

    async function fetchApi(url, options = {}) {
        newChallengeBtn.disabled = true;
        submitBtn.disabled = true;
        somaBtn.disabled = true;
        if (audioFeaturesEnabled) micBtn.disabled = true;
        hintBtn.disabled = true;
        
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: `HTTP Error: ${response.status}` }));
                throw new Error(errorData.detail);
            }
            if (response.headers.get('Content-Type')?.includes('audio/')) {
                return await response.blob();
            }
            return await response.json();
        } finally {
            newChallengeBtn.disabled = false;
            submitBtn.disabled = false;
            somaBtn.disabled = false;
            if (audioFeaturesEnabled) micBtn.disabled = false;
            hintBtn.disabled = false;
        }
    }

    async function getNewChallenge() {
        challengeContent.classList.add('hidden');
        instructionElement.textContent = 'Loading challenge...';
        if (currentGameMode === 'image') {
            instructionElement.textContent = 'Generating a new image, this might take a minute or two...';
        }
        answerInput.value = '';
        feedbackMessage.textContent = '';
        correctAnswerFeedback.textContent = '';
        gusakuzaState = 'done';
        hintBtn.classList.add('hidden');

        try {
            const data = await fetchApi(`/get_challenge?difficulty=1&game_mode=${currentGameMode}`);
            currentChallengeId = data.challenge_id;
            
            if (data.challenge_type === 'gusakuza_init') {
                gusakuzaState = 'intro';
                instructionElement.textContent = "Umukino w'Ibisakuzo";
                sourceTextElement.textContent = "Sakwe sakwe!";
                contextTextElement.textContent = "";
                answerInput.classList.add('hidden');
                submitBtn.parentElement.classList.add('hidden');
                somaBtn.classList.remove('hidden');
            } else {
                answerInput.classList.remove('hidden');
                submitBtn.parentElement.classList.remove('hidden');
                somaBtn.classList.add('hidden');
                if (data.challenge_type === 'gusakuza') {
                    hintBtn.classList.remove('hidden');
                }
                if (data.challenge_type === 'image_description') {
                    sourceTextElement.innerHTML = `<img src="${data.source_text}" alt="Challenge image" class="mx-auto rounded-lg">`;
                    instructionElement.textContent = 'Describe what you see in Kinyarwanda or English.';
                } else if (data.challenge_type === 'text_description') {
                    sourceTextElement.textContent = data.source_text;
                    instructionElement.textContent = 'Read the description and imagine the scene. There is no right or wrong answer.';
                    submitBtn.parentElement.classList.add('hidden');
                } else {
                    sourceTextElement.textContent = data.source_text;
                    instructionElement.textContent = data.challenge_type.includes('kin_to_eng') ? 'Can you speak or type this in English?' : 'Can you speak or type this in Kinyarwanda?';
                }
                contextTextElement.textContent = data.context || '';
            }

            challengeContent.classList.remove('hidden');
        } catch (error) {
            instructionElement.textContent = `Failed to load challenge: ${error.message}`;
            console.error("Error fetching new challenge:", error);
        }
    }

    async function getHint() {
        if (!currentChallengeId) return;

        try {
            const data = await fetchApi(`/get_hint?challenge_id=${currentChallengeId}`);
            feedbackMessage.textContent = `Hint: ${data.hint}`;
            correctAnswerFeedback.textContent = '';
            hintBtn.disabled = true; // Disable after use
        } catch (error) {
            feedbackMessage.textContent = `Error: ${error.message}`;
            console.error("Error fetching hint:", error);
        }
    }

    async function submitAnswer() {
        const userAnswer = answerInput.value.trim();
        if (!userAnswer) return;

        const formData = new FormData();
        formData.append('challenge_id', currentChallengeId);
        formData.append('user_answer', userAnswer);

        try {
            const data = await fetchApi('/submit_answer', { method: 'POST', body: formData });
            
            lives = data.lives;
            score = data.score;
            updateScoreboard();

            feedbackMessage.textContent = data.message;
            correctAnswerFeedback.textContent = data.is_correct ? '' : `Correct answer: ${data.correct_answer}`;
            
            if (audioFeaturesEnabled) {
                const textToSpeak = data.is_correct ? data.message : `${data.message}. The correct answer was: ${data.correct_answer}`;
                await synthesizeAndPlay(textToSpeak);
            }

            if (lives <= 0) {
                alert('Game Over!');
                if(audioFeaturesEnabled) await synthesizeAndPlay("Game Over!");
                lives = 3;
                score = 0;
                updateScoreboard();
            }

        } catch (error) {
            feedbackMessage.textContent = `Error: ${error.message}`;
            console.error("Error submitting answer:", error);
        }
    }

    let socket;

    async function toggleRecording() {
        if (!audioFeaturesEnabled) return;

        if (isRecording) {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
            isRecording = false;
            micBtn.classList.remove('bg-green-500');
            micBtn.classList.add('bg-red-500');
            instructionElement.textContent = 'Recording stopped.';
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

            const wsUrl = `wss://${window.location.host}/ws/transcribe`;
            socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                instructionElement.textContent = 'Recording...';
                mediaRecorder.start(1000); // Send data every 1 second
            };

            socket.onmessage = (event) => {
                answerInput.value = event.data;
            };

            socket.onerror = (error) => {
                console.error('WebSocket Error:', error);
                instructionElement.textContent = 'Error connecting to transcription service.';
            };

            socket.onclose = () => {
                instructionElement.textContent = 'Transcription service disconnected.';
            };

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
                    socket.send(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                if (socket.readyState === WebSocket.OPEN) {
                    socket.close();
                }
                stream.getTracks().forEach(track => track.stop());
            };

            isRecording = true;
            micBtn.classList.remove('bg-red-500');
            micBtn.classList.add('bg-green-500');

        } catch (error) {
            console.error("Error accessing microphone:", error);
            alert("Could not access microphone. Please ensure you have given permission.");
        }
    }

    async function synthesizeAndPlay(text) {
        if (!audioFeaturesEnabled) return;
        try {
            const formData = new FormData();
            formData.append('text', text);
            const audioBlob = await fetchApi('/synthesize', { method: 'POST', body: formData });
            const audioUrl = URL.createObjectURL(audioBlob);
            audioPlayer.src = audioUrl;
            audioPlayer.play();
        } catch (error) {
            console.error("Error synthesizing speech:", error);
        }
    }
}
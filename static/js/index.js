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
    
    const audioPlayer = document.getElementById('audio-player');
    const gameModeSelector = document.getElementById('game-mode-select');
    const hintBtn = document.getElementById('hint-btn');

    updateScoreboard();
    gameModeSelector.value = currentGameMode;
    getNewChallenge();
    
    gameModeSelector.addEventListener('change', () => {
        currentGameMode = gameModeSelector.value;
        getNewChallenge();
    });

    submitBtn.addEventListener('click', submitAnswer);
    newChallengeBtn.addEventListener('click', getNewChallenge);
    somaBtn.addEventListener('click', handleSoma);
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
                } else {
                    sourceTextElement.textContent = data.source_text;
                }
                instructionElement.textContent = data.context || 'Translate the phrase.';
                contextTextElement.textContent = "";
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
            hintBtn.disabled = true;
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
            correctAnswerFeedback.textContent = ""; // Clear this as the new message contains everything
            
            if (audioFeaturesEnabled) {
                await synthesizeAndPlay(data.message);
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

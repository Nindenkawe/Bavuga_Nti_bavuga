# Bavuga Ntibavuga - A Blueprint for Modern Generative AI Applications

## Overview

Building applications with large language models like Google's Gemini can be incredibly powerful, but it's easy to fall into the trap of creating messy, hard-to-maintain code. **Bavuga Ntibavuga** is a language learning game that serves as a blueprint for how to build clean, modular, and scalable AI-powered applications.

This project demonstrates that getting started with generative AI doesn't have to be complicated. By using the right tools and architecture, you can build sophisticated features faster and more reliably.

At the heart of this project is the **`genai-processors`** library, which allows us to structure our AI interactions in a simple, powerful, and pythonic way.

## The Core Idea: Modular AI Processors

Instead of making direct API calls to the Gemini model from all over the codebase, we've adopted a **processor model**. Each specific AI task is encapsulated in its own `Processor` class. Think of them as specialized "AI workers":

-   `ChallengeGeneratorProcessor`: Its only job is to create new game challenges.
-   `AnswerEvaluatorProcessor`: Its only job is to evaluate a user's answer.
-   `StreamingAudioProcessor`: Its only job is to handle live audio transcription.

This approach, enabled by the `genai-processors` library, makes our application:
-   **Easy to Build:** We can develop and test each AI feature in isolation.
-   **Easy to Read:** The logic is clean and organized, not tangled together.
-   **Easy to Maintain:** If we want to improve challenge generation, we only need to edit one file.

## Powerful Prompting Made Easy

Getting high-quality responses from an AI model depends entirely on the quality of your prompts. This project uses several key **prompt engineering** techniques to get structured, relevant, and reliable results.

The `genai-processors` architecture makes implementing these techniques incredibly straightforward:

-   **Grounding:** We give the AI a clear role and a set of constraints. For example, our `AnswerEvaluatorProcessor` is told, "You are an expert in Kinyarwanda and English... Respond ONLY with 'Correct' or 'Incorrect'." This prevents conversational, ambiguous answers and gives us a reliable, programmatic output.

-   **Few-Shot Prompting:** We give the model an example of the exact output format we want. For our translation challenges, we include a line like `Example: 'Where is the bathroom?|Bwihereho ni he?'`. This simple trick dramatically improves the consistency and structure of the AI's response.

-   **Chaining & Composition:** Our `GameProcessor` acts as a pipeline, receiving a request and routing it to the correct specialized processor. This allows us to compose complex workflows from simple, reusable blocks.

## Getting Started

To run the application on your local machine and explore the code, please refer to our detailed developer's guide:

**[>> Go to the Developer's Deep Dive Guide (MLOps/sessionguide.md)](MLOps/sessionguide.md)**

The guide provides a complete walkthrough for setting up the project in both a simplified development mode (with mock AI processors) and a full production environment with Docker.

## A Note on AI-Powered Evaluation

A key feature of this application is that the Gemini model itself determines if a user's answer is correct. There isn't a hardcoded set of rules for the translations; the AI handles the linguistic evaluation. This demonstrates the potential of using generative models for complex, "human-like" evaluation tasks. The quality of this evaluation will continue to improve as underlying models are trained with more diverse and domain-specific data.
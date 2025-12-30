# Audio Multimodal vs Traditional ASR

AI Transcription Notepad uses audio multimodal models rather than traditional ASR pipelines.

## Traditional Approach

A typical speech-to-text workflow requires two steps:

1. An ASR model (Whisper, Deepgram, etc.) converts audio to raw text
2. An LLM (GPT-4, Claude, etc.) cleans up the raw transcription

This means two API calls, sequential latency, and the cleanup model only sees the text, not the original audio.

## Multimodal Approach

Audio multimodal models like Gemini, GPT-4o Audio, and Voxtral can directly process audio input. When you send both audio and a cleanup prompt, the model listens to the audio, reads the instructions, and produces formatted output in one pass.

## Why Multimodal Works Better for This Use Case

With multimodal, the AI actually "hears" your recording. It can distinguish between similar-sounding words based on context, understand tone and emphasis, and follow verbal corrections naturally. When you say "scratch that" or "new paragraph," the model understands these as commands because it hears them in context rather than parsing transcribed text.

A single API call also means lower latency and simpler integration.

## When Traditional ASR Makes Sense

Multimodal isn't always the better choice. For bulk transcription without cleanup, dedicated ASR can be faster and cheaper per minute of audio. Traditional ASR models can also be fine-tuned for specialized domains like medical terminology or legal jargon. Some ASR models like Whisper can run fully offline, while multimodal models require cloud APIs.

## AI Transcription Notepad's Approach

AI Transcription Notepad is designed specifically for the multimodal workflow: record audio, optionally process it through VAD and compression, then send it with a cleanup prompt to a multimodal model. The cleanup prompt instructs the model to transcribe, remove filler words, add punctuation and paragraphs, follow verbal instructions, and format as markdown, all in a single pass.

# Voice Notepad Iteration: Cloud API Integration

Here are some notes for context for what I want to try in this iteration of the voice notepad idea, which remains a central tool that I've been working on and going through some different iterations with.

With between local inference and remote inference, and probably tending mostly as in this example coming back to remote inference or using cloud APIs, basically, in order to transcribe.

Now, what I'd like to do in this particular project is the central tool that I'm looking for and use every day is a voice notepad. So basically, a UI for Ubuntu Linux, probably easily be adapted to other platforms with functions for recording your voice. So record, pause, stop, delete, basic recording controls, microphone selection, and then sending that for transcription, and it appearing into a text box.

That's the fundamental thing that we want to do.

Now, what I want to do in this one as opposed to previous versions, which I've been using speech-to-text models, is using audio multimodal models that support audio as an input modality.

And what I want to do is combine the transcription with an instruction for cleaning up the text.

Which is the single phase that was two phases in the previous one, which was ASR and then large language model. So that's why I want to create this one. It's a consolidated cleanup tool.

## Model Selection

So there's—I created a list earlier this week of different models that are out there that support this and in order for this to work, you need a multimodal model which supports audio token processing as well as prompt processing.

And what I'd like for this tool is that we should have a standard what I call a cleanup prompt that's baked in. And it's approximately this: Your task is to provide a cleaned transcription of the audio recorded by the user, remove filler words, add sentences and add natural paragraph spacing. And if the user makes any instructions in the course of the transcription, such as don't include this or change this, include that in the transcription and add subheadings if it's a lengthy transcription. So the idea—that's the end of the prompt. So the idea is that there will be in the background this kind of standard guiding system prompt and that gets sent together with the audio to the model.

So there's two ones that I'd like to use as starters that I know work reliably well. The first is and I'll initially create these as .env variables in the repository, but the ultimate objective is that we'll build this out to a Debian that anyone can use and therefore we should build the app with some basic system for storing safely these keys on the user's local file system. So but we'll start with Gemini and OpenAI. I'll provide the exact model names because that's very important as they've recently changed.

For Gemini, we can use Gemini 2.5 Light preview. In fact, it'll be good to give the user options. So I'll provide the actual APIs for Gemini and for OpenAI.

The third one that I'd like to offer and there is in my list that I gathered this week. The ones are kind of viable outside of Gemini and OpenAI. The challenge is it becomes a little bit harder to find inference providers. And sometimes the audio multimodal models, the only way to get that kind of the workflow I'm describing where you have audio data together with a prompt, is actually to use a chat endpoint and they maintain a classic audio transcription endpoint, which will just do raw transcription, which again kind of defeats the purpose from this implementation standpoint.

## Mistral Integration

But the third one that I think would be useful to include is a model called Voxtral (V-O-X-T-R-A-L). This was released by Mistral AI and I looked at their API docs yesterday and it seemed that I think it's the chat endpoint that's required. But it's very cost effective and it's built for this. So what I'd like to do is if it's possible if we can get the first two running, let's also add Voxtral support. And let's use the larger of their two models, the 24B one. I think it's called small. And we'll use the Mistral API directly. So that would require of course a Mistral API key. And that would round off the initial implementation.

And this is designed for use for kind of quick use. I'm on a Wayland Linux KDE Plasma. It would be great if we had the ability to as a mode setting to type to insert the text into any place where the user has text. But that in my experience is a little challenging with getting virtual inputs to work, but I'm just noting it as a down the line feature. And the other feature that might be more immediately viable and would be very useful would be automatically copy into clipboard. But I think by default in at least in the initial one, let's just have it goes into a text box and there's just a button to copy.

And finally, we should have the idea is that this is a tool that would be used very, very, very frequently throughout the day and something like just to make it easy to start a new note.

The final thing I keep adding on little ideas is cost tracking because it's obviously going to incur cost to be using this. I don't know how easy it is to get if let's assume there's a unique API key in Gemini and in OpenAI for this app. So we can just say everything this key is spending is app activity. And then we could have maybe like spend today, spend this week, spend this month to allow the users to kind of keep on top of their spend and know what they're spending. But that again is kind of more like a little bit of a down the line feature I'd say if it's hard to integrate, but I'm just capturing all of these in the initial spec so we can just have a wide definition and then iterate upon these features. So the core ones to start with would just be the transcription and I'll add my API keys and let's start developing it.

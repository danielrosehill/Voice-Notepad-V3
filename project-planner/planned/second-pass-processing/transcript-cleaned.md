# Voice Note: Second Pass Processing (Cleaned Transcript)

**Recorded:** 31 Dec 2025

---

Okay, this is the first voice note in the repository. Today is the 31st of December, 2025, and this is the voice notepad as it currently stands. I've tried to get a number of these running over the course of the past year, and this is probably the best implementation so far. Actually, the one that I actually now I feel like I'm sticking as in the others were kind of proof of concepts, and this is actually something that I am really building out and using.

I was trying to call up my analytics that I have, and today's one is wow, 207, 207,000 words I've transcribed to date using this app, and I've done 2,383 transcriptions. So quite a sizable test and it's been extremely cost-effective and extremely useful.

These notes are planning out at this point everything, all the basics are in place in terms of what I wanted to get from it, and now I have the luxury of being able to think of little other bits and pieces to add in.

### Text Correction

Here's the first one of those. We can call this text correction.

So the prompt, the concatenated prompt that gets sent to Gemini for that gets constructed through the prompt stack, defining format, tone, style, or in most cases just the general prompt, works in general very, very well. But there are edge cases of failure.

The failures are basically all related to getting keywords wrong or names wrong that might be properly attributable to sloppy pronunciation on my part. But as an example, Claude Code, frequently referring to that tool, if I say it slowly, like Claude Code, it will probably get it right. If I say Claude Code or anyway, it commonly comes back as Clyde Code (C-L-Y-D).

Another one is Open Router as in the API tool for routing requests to large language models. That frequently comes back as Open Rider (R-I-D-E-R). So there are a couple of ones that are kind of commonplace enough and recurrent enough that would motivate me to actually create a rule.

The reason that I don't want to do that traditional approach is because I guess this whole app is kind of taking a more a slightly more unique direction for transcription, starting with using a multimodal model instead of an ASR model. And likewise, my issue with the word replacement tools are that trying to use this stuff every day, they're a bit clunky because you they're not a lot of fun to maintain and update your error list. They tend not to be portable, and so I don't want to create another tool like that.

### Potential Solutions

The solution that sort of comes to my mind at the moment is the other issue I think with those predictive that method is that it's it's impossible to predict what these tools are going to get wrong. Sometimes it's it's surprising. So if I just define a list of predictions or word replacements, it's always going to be kind of imperfect, and I'll always have to be playing catch-up with random mistakes that the model makes in transcription.

I think that a smarter approach is a second pass large language model. I think there's only so much that can be done with system prompting and telling the model, you know, just to do transcribe stuff accurately, it's still going to make these mistakes.

The second pass, there are a few options here, and I'm just the reason that I'm creating this as a note is to kind of just jot them down and jot them out. The first one, the heaviest, the heaviest one from an API perspective is just to send it back.

Sending it back meaning sending the original audio together with the first transcript back to Gemini, saying or whatever, saying, "You got stuff wrong, pay attention to what the user said." Try harder, basically.

That's implementation one. Implementation two is not sending the audio and just sending the text and saying, "Gemini, something about this text contains a something that you transcribed from audio and you got it wrong. Can you use your reasoning to figure out what that is?" I might say, "Oh yeah, open Rider in the context of a discussion about coding, that should definitely have been Open Router and it'll send back the corrected transcript."

I tend towards version two because, firstly, it's going to be quicker. It's also going to be more cost-effective. Not that that, these costs here are very marginal, but quicker is the big draw for that one for me that you that it could be like a fix button that the user uses without having to when you have to add a prompt like, you say what's wrong with the text at that point, you may as well just fix it yourself.

If it's a quick, if it's a lightning-quick button that just says fix, it sends it up in a flash, sends our prompt text up and down. That's a case where it might be helpful.

### Preventive Measures

The final one, and I as I say this I tend to the third one that I'll just add for the the sake of completion, but I don't like it. I don't like the idea of it. I'm trying to avoid this is a cloud AI tool. I don't really like using local stuff for voice that much, although we're using local VAD.

A small model basically. So, not sending it up to something big like Gemini for this task, using something small, and I think that probably makes more sense for the second option, actually. Sending it to the same model again is almost counterintuitive. It's saying, "You got it wrong, the same guy, you know, have it have a second go." I think it could be a small model like Llama or something very, you know, fine-tuned on identifying mistranscriptions by certain context and fixing them.

That's probably the one that makes the most sense to me. That would add speed again over Gemini, and it's another one of those edge cases where it probably could be run locally. But doing so then means it's more complicated to set this up because you've another model to pull, install. VAD is already local. That one makes sense. VAD makes sense locally. I'm not sure that this makes sense. But that would involve adding one more tool to the pipeline.

The final idea here is to kind of try to make preventive a preventive version of this, which is that every single transcription, or there's an option to send every single transcription for a second pass processing that and that would be a slightly different implementation. There is an important subtlety, it's important nuance that in the second one, the second model would have to know that in all likelihood there isn't anything wrong.

But if there is, do it. The problem with that from an AI engineering standpoint is the models are biased towards making fixes, and that's a hard behavior to mitigate against. You run the risk in that approach, in my experience, of getting a second pass model, a small model that just tears up all the good work of the first model and is a disaster. So, those are the options, first, I guess, significant feature as an add-on to be explored.

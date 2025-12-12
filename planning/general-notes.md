# Audio Multimodal For Transcription: Pricing Challenges

Multimodal models which accept audio tokens as inputs are viable and potentiallly highly advantageous replacements for ASR and STT. 

When Apis allow users to provide audio binary data in addition to textual prompts, the user can offer a determinative prompt to steer the transcription providers. 

Estimating costs for this job is slightly more complicated than using a traditional ASR or STT model, however. 

Prices are generated from two main directions:

- The audio data provided by the user is tokenised and billed at an audio tokenisation rate 
- The transcript or edited transcript is provided as text and billed at the text output tokenisation rate

The prompt (or system prompt) is a very minor contributor to the overall cost and for the purpose of simplicity is ignored in these calculations and notes.

## How Should Audio Tokens Be Priced?

This may seem like a fairly simple calculation to benchmark and price. But comparing the apples of audio tokens with other apples is harder than it might appear. 

For one, providers differ in how they charge for these tokens processed. 

One model is to offer a pricing according to the absolute number of tokens that the audio resulted in. This pricing method is transparent only if the audio tokenization method is also transparent and predictable. When this isn't the case, users are left with a substantial amount of confusion as to how much they can expect to pay for a given volume of audio data. 

To negate the unpredictability of this pricing if the audio tokenization model is not disclosed, some providers have opted to provide a per minute price on audio input processed. 

Comparing providers is possible so long as the pricing is transparent!

Gemini is my favorite model for multimodal (and many things in general) because their pricing is clear:

- `flash-latest` which maps onto the latest version of Flash can be thought of as the normal/standard model with fixed rates for text in, audio in, and text out. 
- `flash-lite-*` (replace with variant) provides a cost-effective endpoint where 
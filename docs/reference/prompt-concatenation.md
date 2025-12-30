# Prompt Concatenation Logic

The prompt concatenation logic is the essential mechanism through which the unified formatting instructions are passed to the model to provide a targeted transcription that adheres to a mixture of stylistic and format-specific requirements, while also adhering to basic text cleanup principles.

In addition, the concatenation logic supports the injection of user-specific parameters where doing so achieves useful results. For example, by adding the user's name and email signature when email is targeted as an output format.

The general concatenation logic assumes a level of basic prompt rewrite that is common to all text transformations, which distinguishes this from the verbatim-by-default approach that traditional speech-to-text models take as an implicit assumption. In this architecture, I've chosen not to even offer verbatim as an option. The foundational rewrite provides the basic level of rewriting, which applies filler word removal, punctuation, and paragraph spacing. These are assumed to be desired across all use cases.

Beyond this foundational set of edits are additional basic formatting edits that do not materially change the text for adherence to a specific format, but which are commonly desired, such as subheadings.

Finally, the third layer builds upon this basic rewriting logic to add as an additional requirement that the text meets a mixture of formatting and stylistic requirements.

Formatting requirements are specific formats that the text should adhere to and refers to specific conventions such as the way in which an email is traditionally formatted or the way in which a social post is formatted. These parameters are based upon a description of what these formats are, and how they are typically written. This can differ significantly between formats. For example, an email is laid out very differently than a social post.

Finally, the formality definition, verbosity definition, and tonality definitions are inserted in order to define a specific target formality. This is essential, given that an email intended for sharing with friends is not written in the same way as one shared with colleagues, and even an internal email might be using a more conservative and measured tone as compared to one that is shared externally.

The objective of the prompt concatenation logic is to develop a temporary system prompt that is sent along with the audio file in order to provide extremely precise and determinative guidance for its generation.
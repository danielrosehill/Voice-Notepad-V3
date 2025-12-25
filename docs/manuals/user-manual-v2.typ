// Define colors first (must be before show rules)
#let theme-blue = rgb(67, 97, 238)
#let windows-blue = rgb(0, 120, 214)
#let linux-yellow = rgb(252, 198, 36)
#let debian-red = rgb(168, 29, 51)
#let openrouter-purple = rgb(99, 102, 241)
#let gemini-blue = rgb(66, 133, 244)
#let openai-purple = rgb(65, 41, 145)
#let mistral-orange = rgb(255, 112, 0)
#let budget-green = rgb(34, 197, 94)
#let standard-blue = rgb(59, 130, 246)
#let premium-purple = rgb(139, 92, 246)
#let wayland-teal = rgb(0, 150, 136)

#set document(
  title: "Voice Notepad User Manual v2",
  author: "Daniel Rosehill",
)

#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: rgb(102, 102, 102))
      #h(1fr) Voice Notepad User Manual v2
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: rgb(102, 102, 102))
      Daniel Rosehill & Claude Code
      #h(1fr)
      github.com/danielrosehill/Voice-Notepad
      #h(1fr)
      Page #counter(page).display()
    ]
  },
)

#set text(
  font: "DejaVu Sans",
  size: 11pt,
)

#set heading(numbering: "1.1")

// Keep content together - avoid orphans
#set block(breakable: true)

#show heading.where(level: 1): it => {
  set text(24pt, weight: "bold", fill: rgb(26, 26, 46))
  pagebreak(weak: true)
  block(below: 1em)[
    #it.body
    #v(0.3em)
    #line(length: 100%, stroke: 2pt + theme-blue)
  ]
}

#show heading.where(level: 2): it => {
  set text(16pt, weight: "bold", fill: rgb(26, 26, 46))
  block(above: 1.5em, below: 0.8em, breakable: false)[
    #it
    #v(0.2em)
    #line(length: 100%, stroke: 0.5pt + rgb(204, 204, 204))
  ]
}

#show heading.where(level: 3): it => {
  set text(13pt, weight: "bold", fill: rgb(45, 52, 54))
  block(above: 1.2em, below: 0.6em)[#it]
}

#show link: it => {
  set text(fill: theme-blue)
  underline(it)
}

// Keep figures with their captions
#show figure: it => block(breakable: false)[#it]

// Badge/pill helper function
#let badge(label, bg-color, text-color: white) = {
  box(
    fill: bg-color,
    inset: (x: 10pt, y: 5pt),
    radius: 4pt,
    text(weight: "bold", size: 10pt, fill: text-color)[#label]
  )
}

// Title Page
#align(center)[
  #v(2cm)
  #text(42pt, weight: "bold", fill: rgb(26, 26, 46))[Voice Notepad]
  #v(0.3cm)
  #text(18pt, fill: rgb(102, 102, 102))[User Manual v2]
  #v(0.5cm)
  #text(14pt)[Application Version 1.8.0]

  #v(1.5cm)

  // Platform badges
  #text(11pt, weight: "bold", fill: rgb(102, 102, 102))[PLATFORMS]
  #v(0.3cm)
  #badge("Windows", windows-blue)
  #h(0.3cm)
  #badge("Linux", linux-yellow, text-color: black)
  #h(0.3cm)
  #badge("Debian", debian-red)
  #h(0.3cm)
  #badge("Wayland", wayland-teal)

  #v(1cm)

  // AI Provider badges
  #text(11pt, weight: "bold", fill: rgb(102, 102, 102))[SUPPORTED AI PROVIDERS]
  #v(0.3cm)
  #badge("OpenRouter", openrouter-purple)
  #h(0.3cm)
  #badge("Google Gemini", gemini-blue)
  #h(0.3cm)
  #badge("OpenAI", openai-purple)
  #h(0.3cm)
  #badge("Mistral AI", mistral-orange)

  #v(1.5cm)
  #image("../../screenshots/by-version/1_5_0/composite-2.png", width: 85%)
  #v(1.5cm)

  #text(12pt)[
    *Author:* Daniel Rosehill \
    *Repository:* #link("https://github.com/danielrosehill/Voice-Notepad")[github.com/danielrosehill/Voice-Notepad] \
    *License:* MIT
  ]

  #v(1cm)
  #text(10pt, fill: rgb(153, 153, 153))[Documentation created with Claude Code]
]

#pagebreak()

// Table of Contents
#outline(
  title: [Table of Contents],
  indent: 1.5em,
  depth: 3,
)

#pagebreak()

= Introduction

Voice Notepad is a desktop application for voice recording with AI-powered transcription and cleanup. Unlike traditional speech-to-text tools that require a separate text cleanup pass, Voice Notepad uses *multimodal AI models* that can process audio directly and perform both transcription and text cleanup in a single operation.

== Why Multimodal?

Most voice-to-text apps use a two-step process: first transcribe with ASR (Automatic Speech Recognition), then clean up with an LLM (Large Language Model). Voice Notepad sends your audio directly to multimodal AI models that can hear and transcribe in a single pass.

This matters because:

- *The AI "hears" your tone, pauses, and emphasis* rather than just processing raw text
- *Verbal editing works naturally:* Say "scratch that" or "new paragraph" and the model understands
- *Faster turnaround:* One API call instead of two
- *Lower cost:* Single inference pass

== Key Features

- *One-shot transcription + cleanup:* Audio is sent with a cleanup prompt to multimodal models
- *Multiple AI providers:* OpenRouter (recommended), Gemini, OpenAI, and Mistral
- *File transcription:* Upload audio files (MP3, WAV, OGG, M4A, FLAC)
- *Audio compression:* Automatic downsampling to reduce file size and API costs
- *Voice Activity Detection (VAD):* Optional silence removal before upload
- *Automatic Gain Control (AGC):* Normalizes audio levels for consistent results
- *Cost tracking:* Monitor your API spending in real-time
- *Transcript history:* All transcriptions are saved locally with full-text search
- *Global hotkeys:* System-wide shortcuts that work even when minimized
- *Prompt Stacks:* Layer multiple AI instructions for complex workflows
- *Email personalization:* Business and personal email signatures
- *Text injection:* Automatically paste transcriptions at cursor (Wayland)
- *Append mode:* Record multiple clips and combine before transcription

= Installation

== Download Options

Voice Notepad is available in multiple formats:

#table(
  columns: (auto, auto, 1fr),
  inset: 10pt,
  align: (left, left, left),
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(
    text(fill: white)[*Format*], text(fill: white)[*Platform*], text(fill: white)[*Description*],
  ),
  [`.exe`], [Windows], [Windows installer],
  [`.zip`], [Windows], [Portable Windows version],
  [`.AppImage`], [Linux], [Universal Linux package (runs anywhere)],
  [`.deb`], [Debian/Ubuntu], [Native Debian package],
  [`.tar.gz`], [Linux], [Portable archive],
)

Download the latest release from: #link("https://github.com/danielrosehill/Voice-Notepad/releases")

== System Requirements

- *Operating System:* Windows 10+ or Linux
- *Python:* 3.10+ (for running from source)
- *Audio:* Working microphone
- *Internet:* Required for API calls

== Linux Dependencies

```bash
sudo apt install python3 python3-venv ffmpeg portaudio19-dev
```

== Running from Source

```bash
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad
./run.sh
```

The script creates a virtual environment using `uv` and installs dependencies automatically.

= Getting Started

== Configure API Keys

Before using Voice Notepad, you need to set up at least one API key:

+ Click the *Settings* button in the top-right corner
+ Go to the *API Keys* tab
+ Enter your API key for your preferred provider

*Recommended:* Use #badge("OpenRouter", openrouter-purple) for access to multiple models with a single API key and accurate cost tracking.

== Select Your Provider and Model

On the Record tab:
+ Choose your *Provider* from the dropdown (OpenRouter, Gemini, OpenAI, Mistral)
+ Select your preferred *Model* from the model dropdown
+ Use *Standard* or *Budget* tier buttons for quick model switching

== Start Recording

+ Click *Record* or press `Ctrl+R`
+ Speak into your microphone
+ Click *Transcribe* or press `Ctrl+Return` when finished
+ Your cleaned transcription will appear in the text area

== Copy or Save

- Click *Copy* to copy to clipboard
- Click *Save* to save to a file
- Enable *auto-copy* in Settings to automatically copy after transcription

= Main Interface

Voice Notepad uses a tabbed interface with several main sections. The recording controls are always visible at the top of the window across all tabs.

== Persistent Control Bar

The control bar at the top of the window contains:

- *Status indicator:* Shows current state (Ready, Recording, Processing, etc.)
- *Duration timer:* Shows recording length
- *Segment count:* Shows number of cached segments in append mode
- *Record button:* Start a new recording
- *Pause button:* Pause/resume recording
- *Append button:* Record additional audio to combine with cached audio
- *Stop button:* Stop recording and cache audio
- *Transcribe button:* Send cached audio for transcription
- *Delete button:* Clear current recording and cached audio

== Record Tab

#figure(
  image("../../screenshots/by-version/1_5_0/1-record.png", width: 75%),
  caption: [The Record tab - main transcription interface],
)

The Record tab is where you perform transcriptions.

*Model Selection:*
- *Provider dropdown:* Select your AI provider
- *Model dropdown:* Choose the specific model
- *Standard/Budget buttons:* Quick tier switching

*Favorites Bar:*
- Quick access to your favorite format presets
- Configure favorites in Settings → Personalization

*Prompt Controls:*
- *Format preset:* Select output format (General, Email, Todo, etc.)
- *Formality:* Casual, Neutral, or Professional tone
- *Verbosity:* Control how concise the output should be

*Output Area:*
- View your transcribed text with markdown rendering
- Toggle between *Rendered* view and *Source* editing
- Word and character count displayed

*Actions:*
- *Clear:* Clear the text area
- *Save:* Save transcription to a file
- *Copy:* Copy to clipboard
- *Rewrite:* Send text back to AI for further editing

== File Transcription Tab

Transcribe existing audio files without recording.

*Supported Formats:*
- MP3, WAV, OGG, M4A, FLAC

*Features:*
- Drag and drop files or click to browse
- Multiple file selection
- Same prompt options as recording
- All transcriptions saved to history

== History Tab

The History tab provides access to all your past transcriptions.

*Features:*
- *Full-text search:* Search across all transcriptions
- *Click to preview:* Single-click shows preview
- *Double-click to load:* Load transcription into editor
- *Delete individual:* Remove specific transcriptions
- *Delete All History:* Clear entire history with confirmation

*Statistics:*
- Total transcription count
- Database size
- Audio archive size (if enabled)

== Cost Tab

#figure(
  image("../../screenshots/by-version/1_5_0/3-cost.png", width: 75%),
  caption: [The Cost tab - API usage tracking],
)

The Cost tab provides detailed API usage tracking.

*Account Balance* (OpenRouter only):
- Shows your available credit balance
- Displays total credits and usage

*This API Key's Usage:*
- *Today:* Current day spending
- *This Week:* Weekly spending total
- *This Month:* Monthly spending total
- *All Time:* Lifetime spending

*Local Statistics:*
- Transcription count
- Total words and characters processed

*Export:*
- Export history to CSV (all or date range)

== Prompt Stacks Tab

Prompt Stacks allow you to layer multiple AI instructions for complex transcription scenarios.

*Use Cases:*
- Meeting notes with action items extraction
- Technical documentation with code formatting
- Multi-language transcription with translation
- Custom workflows for recurring tasks

*Features:*
- Create and save named prompt stacks
- Combine multiple prompts that stack together
- Import/export as JSON for sharing
- Toggle between legacy format system and prompt stacks

= Settings

Access settings by clicking the *Settings* button in the top-right corner.

== API Keys

#figure(
  image("../../screenshots/by-version/1_5_0/settings-1-api-keys.png", width: 55%),
  caption: [API Keys configuration],
)

Configure your API keys for each provider:
- #badge("OpenRouter", openrouter-purple) *API Key:* Unified multi-provider access (recommended)
- #badge("Gemini", gemini-blue) *API Key:* Direct Google AI access
- #badge("OpenAI", openai-purple) *API Key:* Direct OpenAI access
- #badge("Mistral", mistral-orange) *API Key:* Direct Mistral access

API keys are stored locally in `~/.config/voice-notepad-v3/config.json`.

== Audio Settings

#figure(
  image("../../screenshots/by-version/1_5_0/settings-2-audio.png", width: 55%),
  caption: [Audio settings configuration],
)

Configure audio-related options:
- *Preferred microphone:* Select your primary input device with optional nickname
- *Fallback microphone:* Backup device if preferred is unavailable
- *Sample rate:* Audio quality settings (default: 48kHz)

== Behavior Settings

#figure(
  image("../../screenshots/by-version/1_5_0/settings-3-behavior.png", width: 55%),
  caption: [Behavior settings configuration],
)

Customize app behavior:
- *Enable VAD:* Voice Activity Detection removes silence before upload
- *Enable AGC:* Automatic Gain Control normalizes audio levels
- *Auto-copy to clipboard:* Automatically copy transcriptions
- *Auto-paste (text injection):* Paste transcription at cursor after copy (requires `ydotool` on Wayland)
- *Archive audio:* Save Opus copies of recordings (~24kbps)
- *Start minimized:* Start the app minimized to tray
- *Audio feedback:* Play beeps on recording start/stop

== Personalization

Configure user-specific settings:
- *User name:* Your name for email signatures
- *Business email:* Email address for professional communications
- *Business signature:* Full signature block for business emails
- *Personal email:* Email address for personal communications
- *Personal signature:* Signature for personal emails
- *Favorite formats:* Quick-access format presets for the main UI

== Database

Database management options:
- *Statistics:* Total transcriptions, database size, archive size
- *FTS Status:* Shows if Full-Text Search is enabled
- *Optimize Database:* Run VACUUM to reclaim disk space
- *Refresh Statistics:* Update the displayed numbers

= Format Presets

Voice Notepad includes many format presets organized by category:

== Foundational
- *General:* No specific formatting---general cleanup only
- *Verbatim:* Minimal transformation, closest to verbatim transcription

== Stylistic
- *Email:* Professional email format with greeting and sign-off
- *Meeting Notes:* Structured notes with action items
- *Bullet Points:* Concise bullet point list
- *Internal Memo:* Company memo format
- *Press Release:* Corporate press release structure
- *Newsletter:* Email newsletter content

== Prompts
- *AI Prompt:* General AI assistant instructions
- *Development Prompt:* Software development instructions
- *System Prompt:* AI system prompt (third-person)
- *Image Generation Prompt:* Prompts for AI image generators

== To-Do Lists
- *To-Do:* Checkbox task list format
- *Shopping List:* Categorized shopping list
- *Grocery List:* Categorized grocery list

== Documentation
- *Documentation:* Clear, structured documentation
- *Technical Docs:* Technical documentation and guides
- *README:* GitHub-style README
- *Reference Doc:* Quick-lookup reference material
- *API Documentation:* API endpoint documentation
- *SOP:* Standard Operating Procedure
- *Changelog:* Software release changelog

== Creative & Experimental
- *Blog Post:* Full blog post with sections
- *Social Post:* Social media post
- *Story Notes:* Creative writing notes
- *Shakespearean Style:* Elizabethan English style
- *Pirate Speak:* Pirate vernacular

= Global Hotkeys

Global hotkeys work system-wide, even when Voice Notepad is minimized or unfocused.

== Current Hotkey Mapping (F15-F19)

#table(
  columns: (auto, auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Key*], text(fill: white)[*Action*], text(fill: white)[*Description*]),
  [F15], [Simple Toggle], [Start recording, or stop and transcribe immediately],
  [F16], [Tap Toggle], [Start recording, or stop and cache audio (for append mode)],
  [F17], [Transcribe Only], [Transcribe cached audio without starting a new recording],
  [F18], [Clear/Delete], [Delete current recording and clear all cached audio],
  [F19], [Append], [Start a new recording that appends to cached audio],
)

== Workflows

*Simple Workflow (F15 only):*
+ Press *F15* to start recording
+ Press *F15* again to stop and transcribe

*Append Workflow (F16/F17/F19):*
+ Press *F16* to start recording
+ Press *F16* again to stop and cache (audio is held in memory)
+ Press *F19* to record another segment (appends to cache)
+ Press *F17* to transcribe all cached segments together
+ Press *F18* to clear cache and start over

== Setting Up Hotkeys

Most keyboards don't have F15+ keys. Use *Input Remapper* to map other keys or buttons to these keycodes:

```bash
sudo apt install input-remapper
```

Common remapping options:
- *Pause/Break key* → F15 for toggle recording
- *USB foot pedal buttons* → F15/F17/F18 for hands-free operation
- *Extra mouse buttons* → F15 for quick dictation

== Technical Notes

- On Wayland: Hotkeys work via evdev (reads directly from input devices)
- Requires user to be in the 'input' group for evdev access
- Falls back to pynput/X11 on non-Linux systems

= Keyboard Shortcuts

== In-App Shortcuts

These work when the Voice Notepad window is focused:

#table(
  columns: (auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Shortcut*], text(fill: white)[*Action*]),
  [`Ctrl+R`], [Start recording],
  [`Ctrl+Space`], [Pause/Resume recording],
  [`Ctrl+Return`], [Stop and transcribe],
  [`Ctrl+S`], [Save to file],
  [`Ctrl+Shift+C`], [Copy to clipboard],
  [`Ctrl+N`], [Clear editor],
)

= Audio Pipeline

Voice Notepad processes audio through several stages before sending it to AI models.

== Processing Stages

+ *Recording:* Captures at device's native sample rate (typically 48kHz)
+ *Automatic Gain Control (AGC):* Normalizes audio levels. Target peak: -3 dBFS, max gain: +20 dB
+ *Voice Activity Detection (VAD):* Silero VAD removes silence segments (typically 30-50% reduction)
+ *Compression:* Downsampled to 16kHz mono (matches Gemini's internal format)
+ *API Submission:* Audio is base64-encoded and sent with cleanup prompt
+ *Storage:* Transcripts saved to MongoDB-compatible database

== VAD Parameters

#table(
  columns: (auto, auto),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Parameter*], text(fill: white)[*Value*]),
  [Sample rate], [16kHz],
  [Window size], [512 samples (~32ms)],
  [Threshold], [0.5],
  [Minimum speech], [250ms],
  [Minimum silence], [100ms],
  [Padding], [30ms],
)

= Cost Tracking

Voice Notepad tracks API costs with *OpenRouter providing accurate key-specific costs* from the API.

== Cost Effectiveness

Real usage data using Gemini 2.5 Flash:
- *848 transcriptions* for *\$1.17 total*
- *84,000 words* transcribed and cleaned
- About *\$0.014 per 1,000 words* (1.4 cents)

== Status Bar

Shows "Today: \$X.XXXX (N) | Bal: \$X.XX" when using OpenRouter:
- N = number of transcriptions today
- Bal = remaining OpenRouter credit balance

== OpenRouter Tracking

OpenRouter provides the most accurate cost tracking:
- *Key-specific usage:* Uses `/api/v1/key` endpoint
- *Account balance:* Via `/api/v1/credits`
- *Activity breakdown:* Model usage via `/api/v1/activity`

= Troubleshooting

== No Audio Detected

+ Check that your microphone is connected
+ Verify the correct microphone is selected in Settings → Audio
+ Check system audio settings (PipeWire/PulseAudio)
+ Try a different input device

== Transcription Fails

+ Verify your API key is correct in Settings
+ Check your internet connection
+ Ensure you have credits/quota with your provider
+ Try a different provider or model

== High API Costs

+ Enable VAD (Voice Activity Detection) to remove silence
+ Use Budget tier models when appropriate
+ Keep recordings concise
+ Monitor spending in the Cost tab

== Global Hotkeys Not Working

*On Linux/Wayland:*
+ Ensure you're in the 'input' group: `sudo usermod -aG input $USER`
+ Log out and back in after adding to group
+ Check if input-remapper is properly configured

*General:*
+ Try different key combinations
+ Avoid keys that conflict with other applications

== Text Injection Not Working

+ Ensure `ydotool` is installed: `sudo apt install ydotool`
+ Start the ydotool daemon: `sudo ydotoold &`
+ Check that auto-paste is enabled in Settings → Behavior

== App Won't Start

+ Check system dependencies are installed
+ Verify Python version (3.10+)
+ Try running from terminal to see error messages
+ Reinstall the application

= Storage Locations

All data is stored in `~/.config/voice-notepad-v3/`:

#table(
  columns: (auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Path*], text(fill: white)[*Contents*]),
  [`config.json`], [API keys and preferences],
  [`mongita/`], [MongoDB-compatible transcript database],
  [`usage/`], [Daily cost tracking JSON files],
  [`audio-archive/`], [Opus audio recordings (if enabled)],
  [`models/`], [Downloaded VAD model (silero_vad.onnx)],
)

= Support

- *GitHub Issues:* #link("https://github.com/danielrosehill/Voice-Notepad/issues")
- *Documentation:* #link("https://github.com/danielrosehill/Voice-Notepad/tree/main/docs")

#v(2cm)
#align(center)[
  #line(length: 50%, stroke: 0.5pt + rgb(204, 204, 204))
  #v(0.5cm)
  #text(10pt, fill: rgb(102, 102, 102))[
    Voice Notepad User Manual v2 (Application v1.8.0) \
    Created by Daniel Rosehill & Claude Code \
    MIT License
  ]
]

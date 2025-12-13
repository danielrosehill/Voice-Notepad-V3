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

#set document(
  title: "Voice Notepad User Manual",
  author: "Daniel Rosehill",
)

#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: rgb(102, 102, 102))
      #h(1fr) Voice Notepad User Manual
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
  #text(18pt, fill: rgb(102, 102, 102))[User Manual]
  #v(0.5cm)
  #text(14pt)[Version 1.3.0]

  #v(1.5cm)

  // Platform badges
  #text(11pt, weight: "bold", fill: rgb(102, 102, 102))[PLATFORMS]
  #v(0.3cm)
  #badge("Windows", windows-blue)
  #h(0.3cm)
  #badge("Linux", linux-yellow, text-color: black)
  #h(0.3cm)
  #badge("Debian", debian-red)

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
  #image("../../screenshots/1_3_0/composite-1.png", width: 85%)
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

== Key Features

- *One-shot transcription + cleanup:* Audio is sent with a cleanup prompt to multimodal models
- *Multiple AI providers:* OpenRouter (recommended), Gemini, OpenAI, and Mistral
- *Audio compression:* Automatic downsampling to reduce file size and API costs
- *Voice Activity Detection (VAD):* Optional silence removal before upload
- *Cost tracking:* Monitor your API spending in real-time
- *Transcript history:* All transcriptions are saved locally with metadata
- *Global hotkeys:* System-wide shortcuts that work even when minimized

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

= Getting Started

== Configure API Keys

Before using Voice Notepad, you need to set up at least one API key:

+ Click the *Settings* button in the top-right corner
+ Go to the *API Keys* tab
+ Enter your API key for your preferred provider

*Recommended:* Use #badge("OpenRouter", openrouter-purple) for access to multiple models with a single API key and accurate cost tracking.

== Select Your Provider and Model

On the Record tab:
+ Choose your *Provider* from the dropdown
+ Select your preferred *Model*
+ Choose between *Standard* (balanced) or *Budget* (cost-effective) tiers

== Start Recording

+ Click *Record* or press `Ctrl+R`
+ Speak into your microphone
+ Click *Transcribe* or press `Ctrl+Return` when finished
+ Your cleaned transcription will appear in the text area

= Main Interface

Voice Notepad uses a tabbed interface with seven main sections.

== Record Tab

#figure(
  image("../../screenshots/1_3_0/1-record.png", width: 75%),
  caption: [The Record tab - main transcription interface],
)

The Record tab is where you perform transcriptions.

*Controls:*
- *Provider:* Select your AI provider (#badge("OpenRouter", openrouter-purple) #badge("Gemini", gemini-blue) #badge("OpenAI", openai-purple) #badge("Mistral", mistral-orange))
- *Model:* Choose the specific model for transcription
- *Standard/Budget:* Toggle between quality tiers
- *Prompt Controls:* Expand to customize the cleanup prompt
- *Microphone selector:* Choose your input device

*Recording Buttons:*
- *Record:* Start a new recording (red button)
- *Pause:* Pause the current recording
- *Transcribe:* Stop and send to AI for transcription
- *Delete:* Discard the current recording

*Output Area:*
- View your transcribed text with markdown rendering
- Toggle between rendered view and source editing
- Word and character count displayed

*Actions:*
- *Clear:* Clear the text area
- *Save:* Save transcription to a file
- *Copy:* Copy to clipboard

== History Tab

#figure(
  image("../../screenshots/1_3_0/2-history.png", width: 75%),
  caption: [The History tab - browse past transcriptions],
)

The History tab provides access to all your past transcriptions.

*Statistics:*
- *Total transcriptions:* Number of recordings processed
- *Database size:* Storage used by transcript history
- *Audio archive:* Size of archived audio files (if enabled)

*Features:*
- Click *Open History File* to export history as CSV
- *Refresh* to update statistics
- History file location shown at bottom

== Cost Tab

#figure(
  image("../../screenshots/1_3_0/3-cost.png", width: 75%),
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

*Export History:*
- Export all history or a date range to CSV

== Analysis Tab

#figure(
  image("../../screenshots/1_3_0/4-analysis.png", width: 75%),
  caption: [The Analysis tab - performance metrics],
)

The Analysis tab shows performance metrics.

*Summary (Last 7 Days):*
- Total transcriptions
- Total cost
- Average inference time
- Total words transcribed

*Model Performance:*
Comparison table showing provider, model, usage count, average inference time, characters per second, and total cost.

*Storage:*
- Total database records
- Records with audio archived
- Database and archive sizes
- *Clear All Data* button for cleanup

== Models Tab

#figure(
  image("../../screenshots/1_3_0/5-models.png", width: 75%),
  caption: [The Models tab - available AI models],
)

The Models tab shows all available AI models organized by provider.

*Model Tiers:*
- #badge("Budget", budget-green) Lower cost options
- #badge("Standard", standard-blue) Balanced cost/quality
- #badge("Premium", premium-purple) Highest quality models

*Provider Tabs:*
- #badge("OpenRouter", openrouter-purple) Access Gemini, GPT-4o, and Voxtral through unified API
- #badge("Gemini", gemini-blue) Direct Google AI access
- #badge("OpenAI", openai-purple) Direct OpenAI access
- #badge("Mistral", mistral-orange) Direct Mistral/Voxtral access

== About Tab

#figure(
  image("../../screenshots/1_3_0/7-about.png", width: 75%),
  caption: [The About tab - app information and shortcuts],
)

The About tab provides app information, scope description, and keyboard shortcuts reference.

= Settings

Access settings by clicking the *Settings* button in the top-right corner.

== API Keys

#figure(
  image("../../screenshots/1_3_0/settings-1-api-keys.png", width: 55%),
  caption: [API Keys configuration],
)

Configure your API keys for each provider:
- #badge("Gemini", gemini-blue) *API Key:* For direct Google AI access
- #badge("OpenAI", openai-purple) *API Key:* For direct OpenAI access
- #badge("Mistral", mistral-orange) *API Key:* For direct Mistral access
- #badge("OpenRouter", openrouter-purple) *API Key:* For unified multi-provider access (recommended)

API keys are stored securely in your local configuration.

== Audio Settings

Configure audio-related options:
- *Default microphone:* Select your preferred input device
- *Sample rate:* Audio quality settings
- *Audio compression:* Enable/disable compression before upload

== Behavior Settings

Customize app behavior:
- *Enable VAD:* Voice Activity Detection removes silence
- *Auto-copy to clipboard:* Automatically copy transcriptions
- *Archive audio:* Save Opus copies of recordings
- *System tray:* Minimize to tray on close

== Hotkeys

#figure(
  image("../../screenshots/1_3_0/settings-4-hotkeys.png", width: 55%),
  caption: [Global hotkeys configuration],
)

Configure global hotkeys that work even when the app is minimized.

*Shortcut Modes:*

#table(
  columns: (auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Mode*], text(fill: white)[*Description*]),
  [Tap to Toggle], [One key toggles recording on/off],
  [Separate Start/Stop], [Different keys for each action],
  [Push-to-Talk], [Hold to record, release to stop],
)

*Recommended Keys:* F14-F20 (macro keys) to avoid conflicts with other applications.

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
  [`Ctrl+N`], [New note (clear)],
)

== Global Hotkeys

These work system-wide, even when the app is minimized or unfocused. Configure them in Settings > Hotkeys.

*Default Configuration:*

#table(
  columns: (auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { theme-blue } else if calc.odd(y) { rgb(248, 249, 250) } else { white },
  table.header(text(fill: white)[*Key*], text(fill: white)[*Action*]),
  [F14], [Start recording],
  [F15], [Stop (discard)],
  [F16], [Stop & transcribe],
)

= Troubleshooting

== No Audio Detected

+ Check that your microphone is connected
+ Use the Mic Test tab to verify audio input
+ Check system audio settings
+ Ensure the correct microphone is selected in Settings

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

+ Check hotkey configuration in Settings
+ Try different key combinations
+ On Wayland, ensure XWayland compatibility
+ Avoid keys that conflict with other applications

== App Won't Start

+ Check system dependencies are installed
+ Verify Python version (3.10+)
+ Try running from terminal to see error messages
+ Reinstall the application

= Support

- *GitHub Issues:* #link("https://github.com/danielrosehill/Voice-Notepad/issues")
- *Documentation:* #link("https://github.com/danielrosehill/Voice-Notepad/tree/main/docs")

#v(2cm)
#align(center)[
  #line(length: 50%, stroke: 0.5pt + rgb(204, 204, 204))
  #v(0.5cm)
  #text(10pt, fill: rgb(102, 102, 102))[
    Voice Notepad v1.3.0 \
    Created by Daniel Rosehill & Claude Code \
    MIT License
  ]
]

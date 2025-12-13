#set document(
  title: "Voice Notepad User Manual",
  author: "Daniel Rosehill",
)

#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: rgb("#666666"))
      #h(1fr) Voice Notepad User Manual
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: rgb("#666666"))
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

#show heading.where(level: 1): it => {
  set text(24pt, weight: "bold", fill: rgb("#1a1a2e"))
  block(below: 1em)[
    #it.body
    #v(0.3em)
    #line(length: 100%, stroke: 2pt + rgb("#4361ee"))
  ]
}

#show heading.where(level: 2): it => {
  pagebreak(weak: true)
  set text(16pt, weight: "bold", fill: rgb("#1a1a2e"))
  block(above: 1.5em, below: 0.8em)[
    #it
    #v(0.2em)
    #line(length: 100%, stroke: 0.5pt + rgb("#cccccc"))
  ]
}

#show heading.where(level: 3): it => {
  set text(13pt, weight: "bold", fill: rgb("#2d3436"))
  block(above: 1.2em, below: 0.6em)[#it]
}

#show link: it => {
  set text(fill: rgb("#4361ee"))
  underline(it)
}

// Title Page
#align(center)[
  #v(3cm)
  #text(36pt, weight: "bold", fill: rgb("#1a1a2e"))[Voice Notepad]
  #v(0.5cm)
  #text(18pt, fill: rgb("#666666"))[User Manual]
  #v(1cm)
  #text(14pt)[Version 1.3.0]
  #v(3cm)
  #image("../../screenshots/1_3_0/composite-1.png", width: 90%)
  #v(2cm)
  #text(12pt)[
    *Author:* Daniel Rosehill \
    *Repository:* #link("https://github.com/danielrosehill/Voice-Notepad")[github.com/danielrosehill/Voice-Notepad] \
    *License:* MIT
  ]
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
  fill: (x, y) => if y == 0 { rgb("#4361ee") } else if calc.odd(y) { rgb("#f8f9fa") } else { white },
  table.header(
    [*Format*], [*Platform*], [*Description*],
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

1. Click the *Settings* button in the top-right corner
2. Go to the *API Keys* tab
3. Enter your API key for your preferred provider

*Recommended:* Use OpenRouter for access to multiple models with a single API key and accurate cost tracking.

== Select Your Provider and Model

On the Record tab:
1. Choose your *Provider* from the dropdown
2. Select your preferred *Model*
3. Choose between *Standard* (balanced) or *Budget* (cost-effective) tiers

== Start Recording

1. Click *Record* or press `Ctrl+R`
2. Speak into your microphone
3. Click *Transcribe* or press `Ctrl+Return` when finished
4. Your cleaned transcription will appear in the text area

= Main Interface

Voice Notepad uses a tabbed interface with seven main sections.

== Record Tab

#figure(
  image("../../screenshots/1_3_0/1-record.png", width: 80%),
  caption: [The Record tab - main transcription interface],
)

The Record tab is where you perform transcriptions.

*Controls:*
- *Provider:* Select your AI provider (OpenRouter, Gemini, OpenAI, Mistral)
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
  image("../../screenshots/1_3_0/2-history.png", width: 80%),
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
  image("../../screenshots/1_3_0/3-cost.png", width: 80%),
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
  image("../../screenshots/1_3_0/4-analysis.png", width: 80%),
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
  image("../../screenshots/1_3_0/5-models.png", width: 80%),
  caption: [The Models tab - available AI models],
)

The Models tab shows all available AI models.

*Model Tiers:*
- *Budget* (green): Lower cost options
- *Standard* (blue): Balanced cost/quality
- *Premium* (purple): Highest quality models

*Provider Tabs:*
- *OpenRouter:* Access Gemini, GPT-4o, and Voxtral through unified API
- *Gemini:* Direct Google AI access
- *OpenAI:* Direct OpenAI access
- *Mistral:* Direct Mistral/Voxtral access

== About Tab

#figure(
  image("../../screenshots/1_3_0/7-about.png", width: 80%),
  caption: [The About tab - app information and shortcuts],
)

The About tab provides app information, scope description, and keyboard shortcuts reference.

= Settings

Access settings by clicking the *Settings* button in the top-right corner.

== API Keys

#figure(
  image("../../screenshots/1_3_0/settings-1-api-keys.png", width: 60%),
  caption: [API Keys configuration],
)

Configure your API keys for each provider:
- *Gemini API Key:* For direct Google AI access
- *OpenAI API Key:* For direct OpenAI access
- *Mistral API Key:* For direct Mistral access
- *OpenRouter API Key:* For unified multi-provider access (recommended)

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
  image("../../screenshots/1_3_0/settings-4-hotkeys.png", width: 60%),
  caption: [Global hotkeys configuration],
)

Configure global hotkeys that work even when the app is minimized.

*Shortcut Modes:*

#table(
  columns: (auto, 1fr),
  inset: 10pt,
  fill: (x, y) => if y == 0 { rgb("#4361ee") } else if calc.odd(y) { rgb("#f8f9fa") } else { white },
  table.header([*Mode*], [*Description*]),
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
  fill: (x, y) => if y == 0 { rgb("#4361ee") } else if calc.odd(y) { rgb("#f8f9fa") } else { white },
  table.header([*Shortcut*], [*Action*]),
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
  fill: (x, y) => if y == 0 { rgb("#4361ee") } else if calc.odd(y) { rgb("#f8f9fa") } else { white },
  table.header([*Key*], [*Action*]),
  [F14], [Start recording],
  [F15], [Stop (discard)],
  [F16], [Stop & transcribe],
)

= Troubleshooting

== No Audio Detected

1. Check that your microphone is connected
2. Use the Mic Test tab to verify audio input
3. Check system audio settings
4. Ensure the correct microphone is selected in Settings

== Transcription Fails

1. Verify your API key is correct in Settings
2. Check your internet connection
3. Ensure you have credits/quota with your provider
4. Try a different provider or model

== High API Costs

1. Enable VAD (Voice Activity Detection) to remove silence
2. Use Budget tier models when appropriate
3. Keep recordings concise
4. Monitor spending in the Cost tab

== Global Hotkeys Not Working

1. Check hotkey configuration in Settings
2. Try different key combinations
3. On Wayland, ensure XWayland compatibility
4. Avoid keys that conflict with other applications

== App Won't Start

1. Check system dependencies are installed
2. Verify Python version (3.10+)
3. Try running from terminal to see error messages
4. Reinstall the application

= Support

- *GitHub Issues:* #link("https://github.com/danielrosehill/Voice-Notepad/issues")
- *Documentation:* #link("https://github.com/danielrosehill/Voice-Notepad/tree/main/docs")

#v(2cm)
#align(center)[
  #line(length: 50%, stroke: 0.5pt + rgb("#cccccc"))
  #v(0.5cm)
  #text(10pt, fill: rgb("#666666"))[
    Voice Notepad v1.3.0 \
    Created by Daniel Rosehill \
    MIT License
  ]
]

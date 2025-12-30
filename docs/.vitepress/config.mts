import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Voice Notepad',
  description: 'Desktop app for voice recording with AI-powered transcription and cleanup',

  head: [
    ['link', { rel: 'icon', type: 'image/png', href: '/icon.png' }]
  ],

  themeConfig: {
    logo: '/icon.png',

    nav: [
      { text: 'Guide', link: '/guide/installation' },
      { text: 'Reference', link: '/reference/models' },
      {
        text: 'Download',
        items: [
          { text: 'GitHub Releases', link: 'https://github.com/danielrosehill/Voice-Notepad/releases' },
          { text: 'User Manual (PDF)', link: '/manuals/Voice-Notepad-User-Manual-v3.pdf' }
        ]
      }
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'Hotkey Setup', link: '/guide/hotkey-setup' },
            { text: 'Text Injection', link: '/guide/text-injection' }
          ]
        },
        {
          text: 'Using Voice Notepad',
          items: [
            { text: 'Keyboard Shortcuts', link: '/guide/shortcuts' },
            { text: 'Cost Tracking', link: '/guide/cost-tracking' },
            { text: 'Troubleshooting', link: '/guide/troubleshooting' }
          ]
        }
      ],
      '/reference/': [
        {
          text: 'Technical Reference',
          items: [
            { text: 'Supported Models', link: '/reference/models' },
            { text: 'Audio Pipeline', link: '/reference/audio-pipeline' },
            { text: 'Prompt System', link: '/reference/prompt-concatenation' },
            { text: 'Technology Stack', link: '/reference/stack' },
            { text: 'Multimodal vs ASR', link: '/reference/multimodal-vs-asr' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/danielrosehill/Voice-Notepad' }
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2024-present Daniel Rosehill'
    },

    search: {
      provider: 'local'
    },

    editLink: {
      pattern: 'https://github.com/danielrosehill/Voice-Notepad/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    }
  }
})

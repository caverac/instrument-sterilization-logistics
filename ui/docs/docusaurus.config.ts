import fs from 'node:fs'
import path from 'node:path'

import type * as Preset from '@docusaurus/preset-classic'
import type { Config } from '@docusaurus/types'
import { themes as prismThemes } from 'prism-react-renderer'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'

const baseUrl = process.env.DOCS_BASE_URL ?? '/instrument-sterilization-logistics/'

// Pull the version from the workspace root package.json so the navbar
// badge always reflects the most-recently-released tag (semantic-release
// updates package.json on each release commit).
const rootPkgPath = path.resolve(__dirname, '../../package.json')
const rootPkg = JSON.parse(fs.readFileSync(rootPkgPath, 'utf-8')) as { version?: string }
const projectVersion = rootPkg.version ?? '0.0.0'

const config: Config = {
  title: 'Instrument Sterilization Logistics',
  tagline: 'Cross-facility coordination layer for offsite reprocessing networks',
  favicon: 'img/favicon.svg',

  url: 'https://caverac.github.io',
  baseUrl,

  organizationName: 'caverac',
  projectName: 'instrument-sterilization-logistics',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en']
  },

  stylesheets: [
    {
      href: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css',
      type: 'text/css',
      integrity: 'sha384-nB0miv6/jRmo5UMMR1wu3Gz6NLsoTkbqJghGIsx//Rlm+ZU03BU6SQNC66uf4l5+',
      crossorigin: 'anonymous'
    }
  ],

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn'
    }
  },

  themes: [
    '@docusaurus/theme-mermaid',
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        language: ['en'],
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
        docsRouteBasePath: '/',
        indexBlog: false
      }
    ]
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/caverac/instrument-sterilization-logistics/tree/main/ui/docs/',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex]
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css'
        }
      } satisfies Preset.Options
    ]
  ],

  themeConfig: {
    navbar: {
      title: 'ISL',
      logo: {
        alt: 'ISL logo',
        src: 'img/logo.svg'
      },
      items: [
        {
          type: 'html',
          position: 'left',
          value: `<span class="version-badge">v${projectVersion}</span>`
        },
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Documentation'
        },
        {
          href: 'https://github.com/caverac/instrument-sterilization-logistics',
          label: 'GitHub',
          position: 'right'
        }
      ]
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Overview', to: '/' },
            { label: 'Ingest service', to: '/services/ingest' }
          ]
        },
        {
          title: 'Source',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/caverac/instrument-sterilization-logistics'
            }
          ]
        }
      ],
      copyright: `Copyright (c) ${new Date().getFullYear()} Instrument Sterilization Logistics. Built with Docusaurus.`
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'json', 'yaml', 'sql']
    },
    mermaid: {
      theme: { light: 'neutral', dark: 'dark' }
    }
  } satisfies Preset.ThemeConfig
}

export default config

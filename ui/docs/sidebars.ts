import type { SidebarsConfig } from '@docusaurus/plugin-content-docs'

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Services',
      items: ['services/ingest']
    },
    'roadmap',
    'glossary'
  ]
}

export default sidebars

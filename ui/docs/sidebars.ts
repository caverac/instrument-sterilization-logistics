import type { SidebarsConfig } from '@docusaurus/plugin-content-docs'

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    'local-development',
    {
      type: 'category',
      label: 'Services',
      items: ['services/ingest', 'services/synth-events', 'services/routing', 'services/projector']
    },
    'dashboard',
    'roadmap',
    'glossary'
  ]
}

export default sidebars

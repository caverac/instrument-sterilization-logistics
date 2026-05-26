# instrument-sterilization-logistics

Cross-facility coordination layer for offsite surgical-instrument reprocessing networks. Routes pickups to the facility most likely to hit each OR-case deadline, produces contractually defensible SLA reports across facilities, and learns real tray composition from observed reprocessing data to correct stale preference cards.

See [`notebooks/notes/logs/20260525-idea.md`](notebooks/notes/logs/20260525-idea.md) for the full design.

## Requirements

- [mise](https://mise.jdx.dev/) — manages Node 25, Python 3.14, uv
- [Yarn 4](https://yarnpkg.com/) — bundled via Corepack

## Setup

```bash
mise install
corepack enable
yarn install
uv sync --all-groups
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and code quality standards.

## License

MIT — see [LICENSE](LICENSE).

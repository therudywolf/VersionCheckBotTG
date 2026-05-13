# Security Policy

## Secrets and Local Data

Do not commit `.env`, logs, cache files, SQLite databases, backups, IDE state, or
Python bytecode. The repository ignores these paths by default.

Use `.env.example` as the public template and keep real values only in `.env` or
in your deployment secret store.

If a Telegram bot token, NVD API key, database password, or admin identifier is
exposed, rotate it immediately at the provider and remove the exposed value from
all deployment environments.

## Supported Versions

Security fixes are applied to the current `main` branch.

## Reporting

Open a GitHub issue with reproduction details for non-sensitive security bugs.
For sensitive reports, contact the repository maintainer privately before
publishing details.

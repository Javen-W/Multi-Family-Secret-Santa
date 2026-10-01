---
name: Secret Santa App
overview: Build a typed Python package that loads a participant registry and YAML config, computes a constrained one-to-one Secret Santa assignment, and emails each giver only their recipient.
todos:
  - id: package-skeleton
    content: Add pyproject.toml, package layout, exceptions, logging, and typed models
    status: pending
  - id: config-registry
    content: Implement YAML config and CSV registry loading, cleaning, and validation
    status: pending
  - id: solver
    content: Implement symmetric exclusions, degree-zero pruning, and randomized perfect matching
    status: pending
  - id: email-cli
    content: Implement organizer pairing log, template emailer (SMTP + mock), and CLI entry point
    status: pending
  - id: fixtures-docs
    content: Write config example, dummy registry, README, and docs/ALGORITHM.md plus ARCHITECTURE.md
    status: pending
  - id: tests-notebook
    content: Add pytest suite and the driver notebook
    status: pending
isProject: false
---

# Multi-Family Secret Santa Implementation

Greenfield package under [`src/secret_santa/`](src/secret_santa/). The spec in [`docs/SPECS.md`](docs/SPECS.md) is the source of truth. [`registry.csv.example`](registry.csv.example) stays as the small example; [`config.yaml.example`](config.yaml.example) is filled in (it is currently empty).

## Behavior

A valid program is a permutation of participants: every person is exactly one giver and exactly one recipient. Self-assignment is forbidden. Groups are labels, not automatic blocks — two people in the same group may be paired.

Exclusions are symmetric even when only one side lists them. If A excludes B, or excludes B's group, then both A→B and B→A are forbidden. Unknown exclusion tokens and duplicates are ignored. Names are unique identifiers after stripping whitespace; comparison is case-sensitive.

Infeasible individuals: iteratively drop anyone who has no legal recipient or no legal giver, and log a warning. That covers people who excluded everyone else. If the remaining set has no perfect matching (Hall's condition fails while degrees are still positive), raise `InfeasibleProgramError` and send no email. Duplicate names, missing `name`/`email`, or a bad config are validation errors, not silent drops.

```mermaid
flowchart TD
  config[Load YAML config]
  registry[Load and clean CSV registry]
  graph[Build allowed giver to recipient edges]
  prune[Drop participants with degree zero]
  match[Randomized perfect matching]
  report[Log pairings and program metadata]
  mail[Email each giver only their recipient]
  config --> registry --> graph --> prune --> match --> report --> mail
  prune -->|empty or singleton| fail[InfeasibleProgramError]
  match -->|no perfect matching| fail
```

## Solver

Bipartite matching: givers on one side, recipients on the other, edge `giver → recipient` only when the pair is allowed. Search with randomized depth-first matching (`random.Random`), optional `seed` in config so tests are reproducible. Shuffle giver order and each adjacency list before search. Family-scale registries do not need an external graph library.

Assignment constraints, written up with equations in [`docs/ALGORITHM.md`](docs/ALGORITHM.md):

- permutation: each person appears once as giver and once as recipient
- no fixed points
- forbidden pairs from the symmetric exclusion closure are absent

## Organizer log

After a successful solve, and before any email is sent, write one well-formatted INFO report. This runs in both mock mode and live mode. It is the organizer record, separate from participant email.

The report includes:

- Program metadata: registry path, price limit, email mode (`mock` or `live`), random seed, participant counts (loaded, removed as infeasible, assigned)
- Validation: ignored exclusion tokens, names of removed participants and why, and checks that the matching is a permutation, has no self-assignments, and respects exclusions
- Every pairing on its own line, sorted by giver name: `Giver (group) -> Recipient (group)`

Use a dedicated reporter in [`src/secret_santa/report.py`](src/secret_santa/report.py) so the format stays stable. Tests capture the log and assert the metadata headings and every pairing are present when `mock_mode` is true and when it is false.

Participant emails still must not reveal a giver. The full pairing list exists only in this organizer log (and the organizer-facing notebook).

## Email

Stdlib `smtplib` only (no vendor SDK). Config holds subject, price limit, body template, SMTP host/port/username/password-or-api-key, from-address, TLS, and `mock_mode`. Mock mode logs that a message was skipped and does not connect. Template placeholders are `{giver_name}`, `{recipient_name}`, and `{price_limit}` only, so a message cannot reveal who is giving to the recipient. Per-email INFO lines name the giver and delivery status, not a second copy of the full matching.

## Layout

- [`src/secret_santa/models.py`](src/secret_santa/models.py) — `Participant`, `Assignment`, `ProgramResult`
- [`src/secret_santa/config.py`](src/secret_santa/config.py) — YAML load and validation
- [`src/secret_santa/registry.py`](src/secret_santa/registry.py) — CSV parse, clean, resolve exclusion tokens to people
- [`src/secret_santa/solver.py`](src/secret_santa/solver.py) — allowed graph, prune, matching
- [`src/secret_santa/report.py`](src/secret_santa/report.py) — organizer log of metadata, validation, and all pairings
- [`src/secret_santa/emailer.py`](src/secret_santa/emailer.py) — render and send or mock
- [`src/secret_santa/logging_config.py`](src/secret_santa/logging_config.py) — formatter and level from config
- [`src/secret_santa/cli.py`](src/secret_santa/cli.py) and `__main__.py` — `python -m secret_santa --config config.yaml`
- [`src/secret_santa/exceptions.py`](src/secret_santa/exceptions.py)
- [`pyproject.toml`](pyproject.toml) — package `secret_santa`, requires Python 3.11+, runtime dep `PyYAML`, dev deps `pytest`. Console script `secret-santa`.
- [`tests/`](tests/) — registry cleaning, symmetric exclusions, permutation invariants, price-limit text, mock email has no giver leak, degree-zero removal, infeasible program error, end-to-end run on the example registry, and the organizer log lists every pairing plus metadata in both email modes
- [`notebooks/run_secret_santa.ipynb`](notebooks/run_secret_santa.ipynb) — load config, solve, show the organizer matching, send mail (mock by default)
- [`registries/dummy_registry.csv.example`](registries/dummy_registry.csv.example) — about 16 people, 4 groups, overlapping exclusions, constructed so a matching exists
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module diagram (mermaid)
- [`docs/ALGORITHM.md`](docs/ALGORITHM.md) — matching model and prune policy
- [`README.md`](README.md) — short install, config, and run instructions

Docstrings on every class and function; type hints throughout. No emojis in code. The default email template may include a single tree or gift marker if it stays plain.

## Config and gitignore

[`config.yaml.example`](config.yaml.example) will set `mock_mode: true`, a sample subject and body, price limit `100`, SMTP placeholders, and `registry_path` pointing at the dummy example. Real [`config.yaml`](config.yaml) stays untracked.

Update [`.gitignore`](.gitignore) so `registries/` contents are ignored but `registries/*.example` is kept (a directory ignore currently overrides `!*.example`). Also ignore `.venv/`, `__pycache__/`, `config.yaml`, and `.pytest_cache/`.

# Multi-Family Secret Santa

Assign each person one Secret Santa recipient when families, or other groups, cannot all be paired with each other. The program reads a participant registry and a YAML config, finds a valid assignment, writes an organizer log, and emails each giver only their own recipient.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.yaml.example config.yaml
```

`config.yaml` is ignored by git so SMTP credentials can stay on the machine that sends mail. The example config runs in mock mode and does not open a network connection.

## Run

From the project root:

```bash
python -m secret_santa --config config.yaml
```

The same command is available as `secret-santa --config config.yaml` after installation.

[notebooks/run_secret_santa.ipynb](notebooks/run_secret_santa.ipynb) is a small driver around `run_program`. Open it from the project root, or from `notebooks/`, with the package installed or `src` on the Python path. The shipped example config stays in mock mode.

```python
from secret_santa import run_program

run_program("config.yaml")
```

## Configuration

[config.yaml.example](config.yaml.example) sets the registry path, gift price limit, currency, random seed, log level, and email settings.

- `seed`: integer for a repeatable assignment, or `null` for a new draw each run.
- `email.mock_mode`: `true` logs delivery and sends nothing. `false` sends through SMTP. [docs/EMAIL.md](docs/EMAIL.md) covers Gmail app passwords and the rest of the email settings.
- `email.template` must contain `{giver_name}`, `{recipient_name}`, and `{price_limit}`. Double any literal braces.

Registry paths in the config are relative to the config file.

## Registry

See [registry.csv.example](registry.csv.example) for a small registry and [registries/dummy_registry.csv.example](registries/dummy_registry.csv.example) for a larger one. Real registries belong in `registries/` and are not committed.

Columns:

| Column | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Unique, case-sensitive identifier |
| `email` | yes | Address that receives this person's assignment |
| `group` | yes, to participate | Social-circle label. A blank or missing group removes that person. Sharing a group does not block pairing |
| `exclusions` | no | Comma-separated names or group labels this person cannot be paired with |

Quote an exclusions list that contains commas: `"Joe,Sarah"`. Duplicate tokens and tokens that match nobody are ignored. A token that matches both a person and a group excludes that person and the whole group.

## Constraints

- Each remaining participant gives one gift and receives one gift.
- Nobody is assigned to themselves.
- An exclusion blocks both directions. If Ada excludes Ben, or excludes Ben's group, Ada cannot give to Ben and Ben cannot give to Ada.
- A participant with no group, or with no legal giver or recipient, is removed and named in the log.
- If the people who remain still have no complete assignment, the program raises an error and sends no email.

## Organizer log

A solved run always writes the same INFO report before any email is attempted, in mock mode and in live mode. The report lists the registry, price limit, email mode, seed, participant counts, ignored exclusion tokens, removed participants, validation checks, and every pairing:

```text
Alice (FamilyA) -> Bella (FamilyB)
```

That full list is for the organizer. A participant email names only that giver's recipient and the price limit.

## Tests

```bash
pytest
```

## Documentation

- [docs/SPECS.md](docs/SPECS.md) is the project specification.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describes the modules.
- [docs/ALGORITHM.md](docs/ALGORITHM.md) describes exclusions, pruning, and matching.
- [docs/EMAIL.md](docs/EMAIL.md) describes Gmail app-password setup and email configuration.

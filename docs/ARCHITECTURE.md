# Architecture

The package in `src/secret_santa/` turns a registry and a YAML config into one gift exchange. A notebook or the command-line interface both call `run_program`.

```mermaid
flowchart TD
  entry[CLI or notebook]
  program[SecretSantaProgram]
  config[ProgramConfig]
  registry[RegistryLoader]
  solver[ExchangeSolver]
  report[ProgramReporter]
  mailer[AssignmentMailer]
  entry --> program
  program --> config
  program --> registry
  program --> solver
  program --> report
  program --> mailer
```

## Modules

| Module | Responsibility |
| --- | --- |
| `config.py` | Load and validate YAML hyperparameters |
| `registry.py` | Clean the CSV and expand exclusion tokens to names |
| `solver.py` | Build the allowed graph, drop impossible participants, and match the rest |
| `report.py` | Write the organizer log of metadata, validation, and every pairing |
| `emailer.py` | Render one message per giver and send it, or skip sending in mock mode |
| `program.py` | Run those steps in order |
| `cli.py` | Parse `--config` and return a process status code |

## Run sequence

```mermaid
flowchart TD
  loadConfig[Load YAML config]
  loadRegistry[Load and clean CSV registry]
  buildGraph[Build allowed giver-to-recipient edges]
  prune[Drop participants with degree zero]
  match[Randomized perfect matching]
  organizerLog[Log pairings and program metadata]
  mail[Email each giver only their recipient]
  fail[InfeasibleProgramError]
  loadConfig --> loadRegistry --> buildGraph --> prune --> match --> organizerLog --> mail
  prune -->|fewer than two people remain| fail
  match -->|no perfect matching| fail
```

Mail is not attempted when matching fails, or when the assignment fails its invariant checks. The organizer log is written for every successful solve, whether `email.mock_mode` is true or false.

## Data kept apart

The organizer log is the only record of the full matching. `AssignmentMailer` renders `{giver_name}`, `{recipient_name}`, and `{price_limit}` for that giver alone. The subject line is not personalized.

Live delivery uses the standard library SMTP client. Mock mode records that the message was skipped and does not open a connection.

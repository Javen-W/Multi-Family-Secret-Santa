# Multi-Family Secret Santa

## Description

This is a Python project that resolves a secret santa gift-exchange program, given a registry with combinatorial constraints.

A secret santa program is where each participant is randomly assigned a single, feasible, recipient to give a gift to at Christmas. This is a one-way connection, meaning that if person B is assigned to person A, person A is not necessarily assigned to person B. Each participant is discretely told who their recipient is, while the giver assigned to them remains anonymous until the day of gift exchange. Each participant must be assigned as giver to exactly one person, and must be assigned as recipient to exactly one person.

There are also constraints that not everybody can be assigned to everyone. This project is intended to handle multiple social circles with overlapping members participating in one gift-exchange program, where some individuals might not want to be paired at all with entire circles or individuals.

## Registry File

- See `registry.csv.example` as an example registry `.csv` file.
- Actual registry `.csv` files will live in `registries/`.
- Each participant (row) in a registry must contain `name` and `email` fields, and optionally `exclusions`. A row must also contain `group` to stay in the program. A blank or missing `group` removes that participant. 
- `name` fields must be unique, and serve as unique identifiers.
- The `exclusions` field may contain a comma-delimited list of zero or more `name` or `group` entries. Duplicates and invalid entries are ignored.
- Multiple participants may share the same `group` field.

## Program Config File

Implement an example `.yaml` config file for program hyperparameters:

1. Email subject line
2. Gift price limit (e.g., $100)
3. Email template body
4. Email API key / settings
5. Email mock mode (no actual emails sent out)
6. Registry file path

Among other appropriate hyperparameters...

## Requirements

1. Written as a professional Python project using good programming standards. 
2. Reads in registry (`.csv`) and config files (`.yaml`).
3. Solves an exchange-program that respects assignment constraints.
4. Each participant is individually emailed with their assigned recipient using the configured template email. There must not be data leakage regarding a participants assigned giver. The email also includes a friendly reminder about the configured price limit.
5. A logger is configured and produces meaningful, well-formatted logs.
6. A unit test suite is implemented to validate invariants, constraints, expected behavior, regressions, integration, etc.
7. Data is validated, handled, and cleaned within reason.
8. Infeasible programs throw errors. Infeasible individuals are handled/removed within reason.
9. Implement a helpful, non-verbose `README.md` file.
10. Any additional, helpful documentation is produced and stored in `docs/`. Use mermaid diagrams and Latex equations where appropriate.
11. Implement a Python notebook `.ipynb` as a convenient project entry-point / driver.
12. Generate an example/default config yaml file.
13. Generate a non-trivial dummy registry file (in addition to the example one) for testing and validation purposes.

## Definitions

1. **Participant**: An individual participating in a program.
2. **Giver**: A participant who is responsible for giving a gift to their assigned recipient.
3. **Recipient**: A participant who is on the recieving-end of a giver.
4. **Exclusion**: A configured entity (participant or group) in which a participant cannot be paired with.
5. **Registry**: A list of participants, meta-data, and constraints for a given program.
6. **Program**: A gift-exchange program instance.

## Constraints

1. Each participant is assigned **exactly one** recipient.
2. Each recipient is assigned to **exactly one** giver.
3. A participant with exclusions can neither be assigned recipients or givers from their exclusion pool. 

## Programming Standards

1. Use strong object-oriented design principles: modularity, non-redundant, elegance, scalability, abstraction.
2. Comment all of your code, especially function and class docstrings.
3. You prefer strongly-typed Python variables.
4. Never use emojis, except for perhaps in the default email template messages.

## File Structure

- Dedicated documentation (markdown) files are encouraged and belong in `docs/`. 
- Programming files belong in `src/`. Organize intelligently into sub-directories.
- Registries belong in `registries/`.


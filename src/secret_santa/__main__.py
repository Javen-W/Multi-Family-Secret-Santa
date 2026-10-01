"""Allow ``python -m secret_santa`` to run the command-line program."""

from secret_santa.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

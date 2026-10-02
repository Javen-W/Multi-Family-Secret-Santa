"""CSV registry loading, cleaning, and exclusion resolution."""

import csv
import logging
from pathlib import Path

from secret_santa.exceptions import RegistryValidationError
from secret_santa.models import IgnoredExclusion, Participant, Registry, RemovedParticipant, is_valid_email

logger = logging.getLogger("secret_santa.registry")

REQUIRED_COLUMNS: frozenset[str] = frozenset({"name", "email"})


class RegistryLoader:
    """Load a participant registry from CSV and resolve exclusion tokens."""

    def load(self, path: str | Path) -> Registry:
        """Read ``path``, clean each row, and expand group exclusions to names.

        A row with a blank or missing ``group`` is removed. That person is not
        matched and is not used when other rows' exclusions are resolved.

        Args:
            path: CSV file with ``name`` and ``email`` columns. ``exclusions`` is
                optional. ``group`` is required for a row to stay in the program.

        Returns:
            Remaining participants, ignored exclusion tokens, and removed rows.

        Raises:
            RegistryValidationError: A required field is missing, a name is duplicated,
                or an exclusions list was not quoted and spilled into extra columns.
        """
        registry_path = Path(path)
        rows = self._read_rows(registry_path)
        if not rows:
            raise RegistryValidationError(f"Registry has no participants: {registry_path}")

        cleaned = [self._clean_row(row, line_number) for line_number, row in rows]
        self._require_unique_names(cleaned)
        kept, removed = self._drop_missing_groups(cleaned)
        participants, ignored = self._resolve_exclusions(kept)
        return Registry(
            path=registry_path.resolve(),
            participants=tuple(participants),
            ignored_exclusions=tuple(ignored),
            removed=tuple(removed),
        )

    def _read_rows(self, path: Path) -> list[tuple[int, dict[str, str]]]:
        """Return ``(line_number, row)`` pairs with normalized headers."""
        if not path.is_file():
            raise RegistryValidationError(f"Registry file not found: {path}")
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, restkey="_extra")
                if reader.fieldnames is None:
                    raise RegistryValidationError(f"Registry is missing a header row: {path}")

                fieldnames = [name.strip().lower() for name in reader.fieldnames if name and name.strip()]
                missing = REQUIRED_COLUMNS - set(fieldnames)
                if missing:
                    joined = ", ".join(sorted(missing))
                    raise RegistryValidationError(f"Registry is missing required column(s): {joined}")

                rows: list[tuple[int, dict[str, str]]] = []
                for raw_row in reader:
                    normalized = self._normalize_row(raw_row, reader.line_num)
                    if normalized is None:
                        continue
                    rows.append((reader.line_num, normalized))
                return rows
        except RegistryValidationError:
            raise
        except (OSError, csv.Error) as exc:
            raise RegistryValidationError(f"Could not read registry {path}: {exc}") from exc

    def _normalize_row(
        self,
        raw_row: dict[str, str | list[str] | None],
        line_number: int,
    ) -> dict[str, str] | None:
        """Strip header names and drop fully empty rows.

        Raises:
            RegistryValidationError: The exclusions field was split across extra columns.
        """
        extra = raw_row.get("_extra")
        if isinstance(extra, list) and any(item.strip() for item in extra if item):
            raise RegistryValidationError(
                f"Row {line_number}: exclusions that contain commas must be quoted."
            )

        normalized: dict[str, str] = {}
        for key, value in raw_row.items():
            if key is None:
                continue
            header = key.strip().lower()
            if header == "_extra":
                continue
            if isinstance(value, list):
                continue
            normalized[header] = "" if value is None else value

        name = str(normalized.get("name", "")).strip()
        email = str(normalized.get("email", "")).strip()
        group = str(normalized.get("group", "")).strip()
        exclusions = str(normalized.get("exclusions", "")).strip()
        if not name and not email and not group and not exclusions:
            return None
        return normalized

    def _clean_row(self, row: dict[str, str], line_number: int) -> Participant:
        """Validate one data row and return a participant with unresolved exclusions."""
        name = str(row.get("name", "")).strip()
        email = str(row.get("email", "")).strip()
        group_text = str(row.get("group", "")).strip()
        if not name:
            raise RegistryValidationError(f"Row {line_number}: name is required.")
        if not email:
            raise RegistryValidationError(f"Row {line_number}: missing email for {name!r}.")
        if not is_valid_email(email):
            raise RegistryValidationError(f"Row {line_number}: invalid email for {name!r}: {email!r}.")

        group = group_text or None
        tokens = _split_exclusion_tokens(str(row.get("exclusions", "")))
        return Participant(
            name=name,
            email=email,
            group=group,
            exclusion_tokens=tokens,
            excluded_names=frozenset(),
        )

    def _drop_missing_groups(
        self,
        participants: list[Participant],
    ) -> tuple[list[Participant], list[RemovedParticipant]]:
        """Drop rows whose group is blank and log each removal."""
        kept: list[Participant] = []
        removed: list[RemovedParticipant] = []
        for participant in participants:
            if participant.group:
                kept.append(participant)
                continue
            logger.warning("Removed participant %s: missing group", participant.name)
            removed.append(RemovedParticipant(participant.name, "missing group"))
        return kept, removed

    def _require_unique_names(self, participants: list[Participant]) -> None:
        """Reject duplicate names. Names are case-sensitive identifiers."""
        seen: set[str] = set()
        for participant in participants:
            if participant.name in seen:
                raise RegistryValidationError(f"Duplicate participant name: {participant.name!r}.")
            seen.add(participant.name)

    def _resolve_exclusions(
        self,
        participants: list[Participant],
    ) -> tuple[list[Participant], list[IgnoredExclusion]]:
        """Expand name and group tokens into excluded participant names.

        A token that matches both a person and a group excludes that person and
        every member of the group. Unknown tokens and self references are ignored.
        """
        names = {participant.name for participant in participants}
        groups: dict[str, set[str]] = {}
        for participant in participants:
            if participant.group is None:
                continue
            groups.setdefault(participant.group, set()).add(participant.name)

        resolved: list[Participant] = []
        ignored: list[IgnoredExclusion] = []
        for participant in participants:
            excluded: set[str] = set()
            for token in participant.exclusion_tokens:
                matched: set[str] = set()
                if token in names:
                    matched.add(token)
                if token in groups:
                    matched.update(groups[token])
                matched.discard(participant.name)
                if matched:
                    excluded.update(matched)
                    continue
                reason = "self" if token in names or token == participant.group else "unknown"
                ignored.append(IgnoredExclusion(participant.name, token, reason))
            resolved.append(
                Participant(
                    name=participant.name,
                    email=participant.email,
                    group=participant.group,
                    exclusion_tokens=participant.exclusion_tokens,
                    excluded_names=frozenset(excluded),
                )
            )
        return resolved, ignored


def _split_exclusion_tokens(raw: str) -> tuple[str, ...]:
    """Split a comma-separated exclusion field, dropping blanks and duplicates."""
    tokens: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)

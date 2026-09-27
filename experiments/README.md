# experiments/

Draft or unsure enquiry build scripts and output — work in progress that
hasn't passed `src/enquiry_validator.py` yet, or has passed it but isn't
confirmed against a live tenant and isn't ready to be presented as a
trustworthy `generated/` entry.

Nothing is promoted to `generated/<module>/` automatically. Promote
manually, per `CLAUDE.md`, once:

1. The build script uses `src/enqgen.py`'s functions (not hand-written JSON).
2. `python3 src/enquiry_validator.py <output>.json` passes clean.
3. Any table/column it depends on that isn't already in `docs/SCHEMA.md` or
   `corpus/confirmed_patterns/` is flagged as unconfirmed in the enquiry's
   notes — don't let a draft's guesses go stale and get treated as fact.

This folder is currently empty. Drop a `<name>.py` build script (and,
optionally, its `.json` output alongside it) here for anything in progress.

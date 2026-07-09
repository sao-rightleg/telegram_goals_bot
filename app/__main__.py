"""Command-line entrypoint for `python -m app`."""

from app.runtime import main


if __name__ == "__main__":
    raise SystemExit(main())

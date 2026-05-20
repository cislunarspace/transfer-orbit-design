from __future__ import annotations

from tod.generates.ephemeris import _conversion


def main(argv: list[str] | None = None):
    return _conversion.main_family("dro", argv)


if __name__ == "__main__":
    main()

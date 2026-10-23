"""Warrior Cats: Clans of the Forest mod tool. Run `python wcmods.py --help`."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from wcmods.cli import main  # noqa: E402

if __name__ == "__main__":
    main(ROOT)

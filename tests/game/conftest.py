"""These tests run in the game, through `python wcmods.py agent test` (docs/agent.md), never under pytest:
`pytest tests/game` collects nothing here, so a stray run can't touch the game. The agent's runner reads
the test_*.py files itself and never this one."""
collect_ignore_glob = ["*.py"]

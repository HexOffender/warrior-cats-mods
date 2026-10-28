-- A throwaway script for tests/game/test_scripts.py: the function below is missing its end, so the script
-- doesn't load, and the studio's card, the mod menu's Overview and the top of the screen should say so.
Game.every(1, function()
    MOD.log("never runs")

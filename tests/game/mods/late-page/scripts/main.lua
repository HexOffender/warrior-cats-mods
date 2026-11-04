-- A throwaway script for tests/game/test_scripts.py: its page is made two seconds after it starts, so wcmods has
-- made the automatic settings page by then. The two share the id "script:late-page", and the later one takes the
-- first one's place: one page, with this one's rows. Half is a whole-numbers box given 2.5, which it gives back as
-- it is until the player changes it, and the bars show their text as it's given.
local half = 2.5
Game.after(2, function()
    MOD.page(function(ui)
        ui.heading("Late page")
        ui.text("Made from a timer")
        half = ui.number("Half", half, { whole = true })
        ui.progress("Done", 0.25, { text = "50% done" })   -- ready-made text, shown as it is
        ui.progress("Full", 0.25, { format = "100%" })     -- not a pattern: shown as it is
        ui.progress("Plain", 0.25)                         -- the percent
    end)
end)

"""The game's tables and words from Lua (Game.tables, Game.words; docs/scripting.md "Tables and words"; the Lua plan's
step 6): the DataTables in memory, one by name and by path, its rows, a row read and changed in place and put back, a
row taken out; the string table's words by key and its keys."""

ITEMS = "/Game/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.DT_QuestObjectsInfo"


def test_lua_tables_read_and_changed(agent):
    """The DataTables in memory (60 or more; the item table with its 412 rows and more, its struct and path); one by name
    and by path the same table, none for a name or path that isn't one; a fight party's row read (Default: three out-of-
    clan cats) and its NumParty changed in place, read back by a fresh lookup and by Game.animals.kinds' own reading of
    the table's rows, then put back."""
    got = agent.lua(f"""
        local list, items = Game.tables.list(), nil
        for _, t in ipairs(list) do if t.name == "DT_QuestObjectsInfo" then items = t end end
        local byName, byPath = Game.tables.get("DT_QuestObjectsInfo"), Game.tables.get("{ITEMS}")
        return {{ count = #list, items = items, same = byName ~= nil and byPath ~= nil and byName:GetAddress() == byPath:GetAddress(),
                 rowNames = #Game.tables.rowNames(byName), rows = #Game.tables.rows("DT_QuestObjectsInfo"),
                 missing = Game.tables.get("DT_NoSuchTable") == nil and Game.tables.get("/Game/Nope/DT_Nope.DT_Nope") == nil,
                 noRow = Game.tables.row(byName, "No such row") == nil }}""")
    assert got["count"] >= 60, got["count"]
    items = got["items"]
    assert items["rows"] >= 412 and items["rowStruct"] == "QuestObjectsInfoDataStruct" and items["path"] == ITEMS, items
    assert got["same"] is True and got["rowNames"] == items["rows"] == got["rows"], got
    assert got["missing"] is True and got["noRow"] is True, got

    got = agent.lua("""
        local row = Game.tables.row("DT_Combat_Generator", "Default")
        local was = row.NumParty
        local out = { was = was, tag = Game.tagName(row.GeneratorTag) }
        out.set = Game.tables.set("DT_Combat_Generator", "Default", "NumParty", 2)
        out.again = Game.tables.row("DT_Combat_Generator", "Default").NumParty
        Game.tables.set("DT_Combat_Generator", "Default", "NumParty", was)
        out.back = Game.tables.row("DT_Combat_Generator", "Default").NumParty
        out.refused = { Game.tables.set("DT_Combat_Generator", "No such row", "NumParty", 2) }
        return out""")
    assert got["was"] == 3 and got["tag"] == "Gameplay.Combat.Generator.Fixed.Default", got
    assert got["set"] is True and got["again"] == 2 and got["back"] == 3, got
    assert got["refused"] == [False, "no such row"], got


def test_lua_a_row_taken_out(agent):
    """A row taken out of the credits' table (DT_CreditsInfo: only the credits screen reads it, and the game loads it
    again when it starts): one row fewer, the row gone, taking it out again refused."""
    got = agent.lua("""
        local names = Game.tables.rowNames("DT_CreditsInfo")
        local last = names[#names]
        local out = { before = #names, removed = Game.tables.removeRow("DT_CreditsInfo", last) }
        out.after = #Game.tables.rowNames("DT_CreditsInfo")
        out.gone = Game.tables.row("DT_CreditsInfo", last) == nil
        out.again = Game.tables.removeRow("DT_CreditsInfo", last)
        return out""")
    assert got["before"] >= 2 and got["removed"] is True and got["after"] == got["before"] - 1, got
    assert got["gone"] is True and got["again"] is False, got


def test_lua_words(agent):
    """The game's words by key (STR_CAT_NAME2_PAW is Emberpaw, the test cat's name), nil for a key the table hasn't; the
    string table's keys (thousands), the cats' name keys by their prefix."""
    got = agent.lua("""
        local all, names = Game.wordKeys(), Game.wordKeys("STR_CAT_NAME")
        local ok = true
        for _, k in ipairs(names) do if k:sub(1, 12) ~= "STR_CAT_NAME" then ok = false end end
        return { word = Game.words("STR_CAT_NAME2_PAW"), none = Game.words("NO_SUCH_KEY_X") == nil, all = #all, names = #names,
                 prefixed = ok, other = Game.words("STR_CAT_NAME2_PAW", "NoSuchStringTable") == nil }""")
    assert got["word"] == "Emberpaw" and got["none"] is True and got["other"] is True, got
    assert got["all"] > 8000 and 2000 < got["names"] < got["all"] and got["prefixed"] is True, got

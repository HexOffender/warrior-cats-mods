# Items

The Items page makes herbs, materials and things to wear of your own. They're real items in the game,
in every game you play, not only in Sandbox mode.

## What it changes in the game

- **Herbs** show in your inventory with their own name, description and icon. Using one does what one of
  the game's own herbs does: heals, gives stamina, makes your team stronger for a fight, cures, or gives
  XP.
- **Materials** show in the inventory too. The medicine cat can ask for them in a recipe, and questlines
  can ask for them or give them as a reward.
- **Accessories** are new looks for the game's neck, body and paw accessories: a colour of your own, or a
  picture you painted. You wear them like the game's.
- **The medicine cat's recipe** lets the medicine cat make your herb or accessory at their bartering.
- **Starting with some** puts a few in the cat you're playing, once.

A model of your own, made in Blender, can give an accessory a new shape, or show a herb or a material
your own way when it lies on the ground. Those, and see-through accessories, need the script loader in
the game, which **Get set up**, on the Mods page, installs.

## A five-minute first try

1. Press **Add an item**.
2. Under **What it is**, type the name *Moon Herb* and the description *Heals a cat under the full moon.*
3. Leave **Starts from** on Marigold Petal, the game's medium healing herb. Under **Using it**, **What it
   does** then says it heals 50 health, the same as Marigold Petal.
4. Under **The medicine cat's recipe**, choose **Add a material…**, then Dandelion, and make it 2.
5. Under **Starting with some**, type 3.
6. Press **Save to mod**, then **Apply and play**.

In the game, open your inventory: three Moon Herbs are there, with Marigold Petal's icon. The medicine
cat makes one more for two Dandelions.

## What you can and can't do

You can:

- make a herb do what any of the game's herbs does. **What it does** lists every one of them in words,
  with the herb that does it: "Heals 50 health (Marigold Petal)", "Heals the whole team 50 health
  (Wintergreen Berries)", "Whole team +50% Strength for the fight (Juniper Poultice)". Choosing one also
  makes your herb usable when that herb is, and for whoever that herb is for: the line under **Starts
  from** says which;
- give it the game's icon, the icon in another colour, another item's icon, or a picture of your own.
  **Save the game's icon to paint over** gives you the game's picture to start from;
- ask for the game's materials, or materials this mod adds, in a recipe (they're listed under "Your
  materials");
- make a new look of any look of a neck, body or paw accessory, in a colour or a picture of your own, and
  let the cat show through it (**Opacity**), as glass of one colour;
- give an accessory a shape of your own, or a herb a look of its own on the ground, under **Advanced:
  shape and place (a model of your own needs Blender)**. **Where it sits** there moves an accessory on
  the cat without Blender. The fold opens by itself when an item has a model or a place.

You can't, yet:

- make a new kind of effect, or a stronger one: each effect is the game's own;
- make new looks for head accessories: the game always shows a head accessory's first look;
- make herbs or materials grow in the forest by themselves. They come from **Starting with some**, a
  recipe, a questline's reward, or a script;
- set an item's rarity: nobody has seen what it changes in the game yet;
- keep an accessory's picture while the cat shows through it: see-through accessories are one colour.

## Did it reach the game?

After **Apply to game**, each item in the list gets a chip: **In the game**, or **Left out**. The item's
own page says why one was left out, or what to know about one that went in ("no save to give it in
yet", "on the ground it's the game's pickup"), and a line at the top counts them: "3 of 4 items went in.
Moon Herb was left out: it has no description, so it's left out of the game." When you open the studio
again later, the chips are the last Apply's, and say when it was. The whole story is in
[the log](studio.md#the-log), under **Last apply**.

In the game, open your inventory. A herb or a material you gave yourself some of is there. One you didn't
shows at the medicine cat's bartering when it has a recipe. An accessory you made is worn from the
inventory like the game's, once you have one.

## Common mistakes

- **No description.** An item needs a name and a description. The page marks an empty one in red, and
  the list says "needs a description". It still saves, and the mod's other items go in, but that one is
  left out of the game until it has one: under the Editing mod bar the save says "Saved. Left out of the
  game until finished: Moon Herb (no description)." A name you leave empty goes back to the item's
  technical name.
- **A recipe with a material that was left out.** A material of this mod's that isn't finished yet (no
  description) is left out, and so is a herb whose recipe asks for it: the log says "Moonstone is one of
  this mod's, left out: no description". Finish the material, and both go in.
- **A name the game already uses.** The page gives a new item a technical name of its own, so "Medium
  Healing Herb" is fine: the studio calls it MediumHealingHerb2 behind the scenes. One made outside the
  studio with the game's own technical name shows it in red under **Technical name**, with **Give it a
  name of its own**.
- **Starting with some, and no save yet.** They go into the cat you're playing when you apply, so start
  the game once first. It happens once: a cat that already has some isn't given more.
- **Changing the Kind.** A herb, a material and an accessory each keep their own settings. Changing the
  kind puts the old ones aside; change it back before you save or leave the page and they come back.
- **An accessory with nothing of its own.** A new look needs a colour, a picture, a model or an opacity of
  its own. Take the last one away and the page puts a colour back, and says so.
- **A model far from the cat.** Models are made in metres, around the cat of the start kit. The page says
  how far yours reaches, and the sliders under **Where it sits** move it into place.

## Undo

Nothing reaches your mod until you press **Save to mod**, and nothing reaches the game until you
apply: see [what Undo means here](studio.md#what-undo-means-here).

- To drop changes you haven't saved, switch to another mod in the Editing mod bar and back.
- **Remove** takes an item out (press it twice). Its pictures and models stay in the mod's folder.
- To take an item out of the game, remove it or switch its mod off on the Mods page, and apply again.

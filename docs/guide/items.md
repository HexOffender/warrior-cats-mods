# Items

The Items page makes herbs, materials and accessories of your own. They're real items in every game you
play, story games too, not only in [Sandbox mode](README.md#sandbox-mode). It saves them as `items.json`
in your mod.

## What it changes in the game

- A herb shows in your inventory with its own name, description and icon. Using it does what one of
  the game's herbs does: heals, gives stamina, makes your team stronger for a fight, cures, or gives XP.
- A material shows in the inventory too. The medicine cat can ask for it in a recipe, and questlines
  can ask for it or give it as a reward.
- An accessory is a new look for one of the game's neck, body or paw accessories: a colour of your own,
  or a picture you painted. You wear it like the game's.
- **The medicine cat's recipe** lets the medicine cat make your herb or accessory at their bartering.
- **Starting with some** puts a few in the cat you're playing, once.

How it gets there: your items go in with your mods when you apply, and the ones you start with are
written into your save. A model of your own (made in Blender or another 3D program) can give an
accessory a new shape, or show a herb or a material your own way when a script or a story drops it on
the ground. Those, and see-through accessories, need the [script loader](README.md#script-loader),
which **Get set up**, on the Mods page, installs.

## A five-minute first try

1. Open Items and press **Add an item**. A herb called "New herb" appears.
2. Under **What it is**, type "Moon Herb" in **Name** and "Heals a cat under the full moon." in
   **Description**.
3. Leave **Starts from** on Marigold Petal. Under **Using it**, **What it does** says "The same as
   Marigold Petal: Heals 50 health".
4. Under **The medicine cat's recipe**, pick Dandelion in **Add a material…**, and make its number 2.
5. Under **Starting with some**, type 3.
6. Press **Save to mod**.
7. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
8. In the game, open your inventory: three Moon Herbs, with Marigold Petal's icon. At the medicine cat's
   bartering, one more costs two Dandelions.

## What you can and can't do

You can:

- make a herb do what any of the game's herbs does. **What it does** lists each in words, with the herb
  that does it: "Heals 50 health (Marigold Petal)", "Heals the whole team 50 health (Wintergreen
  Berries)". Your herb is then used when, and for whom, that herb is: the line under **Starts from**
  says which ("Used anywhere, for you");
- choose the small picture on its icon with **Badge on its icon**;
- give it, under **Icon**, the icon of the item it starts from, that icon in another colour, another
  item's icon, or a picture of your own. **Save the game's icon to paint over** gives you the game's
  picture to start from;
- ask for the game's materials, or this mod's own (under "Your materials"), in a recipe. Only herbs and
  accessories have recipes: the medicine cat doesn't make materials;
- give a new look of a neck, body or paw accessory a colour or a picture of your own (**Look**), and
  let the cat show through it with **Opacity**, as glass in one colour (**Glass colour**);
- under **Advanced: shape and place (a model of your own needs Blender)**: give an accessory a shape of
  your own (**Save a start kit to model on** gives you the cat to make it around), move it on the cat
  with the sliders under **Where it sits** (no Blender needed), or give a herb or a material a model of
  its own **On the ground**. Models are OBJ or glTF (.glb) files. The fold opens by itself when an item
  has a model or a place.

You can't, yet:

- make a new kind of effect, or a stronger one: each effect is the game's own;
- make new looks for head accessories: the game always shows a head accessory's first look;
- make herbs or materials grow in the forest. They come from **Starting with some**, a recipe, a
  questline's reward, or a script;
- set an item's rarity: nobody has seen what it changes in the game yet;
- keep an accessory's picture while the cat shows through it: see-through accessories are one colour;
- see through a model on the ground: its picture is solid.

## Did it reach the game?

After you apply, each item in the list gets a chip: **In the game**, or **Left out**. The top of the
item says why one was left out, or what to know about one that went in ("no save to give it in yet",
"on the ground it's the game's pickup"). A line at the top of the page counts them: "3 of 4 items went
in. Moon Herb was left out: it has no description." An item added since says **Not applied yet**.
**Check my mods** (Settings and repair) puts nothing in the game, so it doesn't change the chips. When
you open the studio again later, the line at the top is the last apply's, with its date. The whole
story is in the [build log](README.md#build-log): **Last apply**, at the top, opens it.

In the game, open your inventory for what you start with. A herb or an accessory with a recipe is at
the medicine cat's bartering. An accessory is worn from the inventory like the game's, once you have
one. At the bartering, an accessory you already have shows as an empty slot; the game's own do that too.

Seen working in the game: herbs and materials in the inventory with their names, descriptions and
icons; their recipes, and trading for them; icons from a picture and recoloured ones; a new collar look
in its own colour; accessories with models of their own, moved, and as glass, on your cat; and models on
the ground dropped by a script. Not checked yet: accessories' models on other cats (the clans' and a
mod's), on a cat the game made brawny or chubby, and in the save slots' pictures; a new look made from
an accessory's second look; and models on the ground from a questline's reward or Sandbox mode's
stories.

## Common mistakes

- No description. An item needs a name and a description. The page marks an empty one in red, and the
  list says "needs a description". It still saves, and the mod's other items go in, but that one is
  left out of the game until it has one: under the Editing mod bar the save says "Saved. Left out of the
  game until finished: Moon Herb (no description)." A name you leave empty goes back to the item's
  technical name.
- A recipe with a material that was left out. A material of this mod's that isn't finished yet (no
  description) is left out, and so is a herb whose recipe asks for it: the build log says "Moonstone is
  one of this mod's, left out: no description". Finish the material, and both go in.
- A name the game already uses. The page gives a new item a technical name of its own, so "Medium
  Healing Herb" is fine: the studio calls it MediumHealingHerb2 behind the scenes. One made outside the
  studio with the game's own technical name shows it in red under **Technical name**, with **Give it a
  name of its own**.
- Starting with some, and no save yet. They go into the cat you're playing when you apply, so start the
  game once first. It happens once: a cat that already has some isn't given more.
- Changing **Kind**. A herb, a material and an accessory each keep their own settings. Changing the
  kind puts the old ones aside; change it back before you leave the page and they come back.
- An accessory with nothing of its own. A new look needs a colour, a picture, a model, a place or an
  opacity of its own. Take the last one away and the page puts a colour back, and says so.
- A model far from the cat. Models are made in metres, around the cat of the start kit. The page says
  how far yours reaches, and the sliders under **Where it sits** move it into place.
- No script loader. Accessories with a model, a place or an opacity of their own show as the game's
  shape, solid, until **Get set up** installs it.

## Undo

Nothing reaches your mod until you press **Save to mod**, and nothing reaches the game until you apply
([what Undo means here](studio.md#what-undo-means-here)).

- Changes you haven't saved: switch to another mod in the Editing mod bar, choose **Switch without
  saving**, and switch back.
- An item: its **Remove** button, at the foot of its card (press it twice). Its pictures and models
  stay in the mod's folder.
- In the game: remove the item, or switch its mod off on the Mods page, and apply again.
- What **Starting with some** gave is in your save, and stays when the mod is off. What the game shows
  for an item whose mod is off hasn't been tried yet. To be sure, switch the mod off, then on
  [Settings and repair](settings.md), under **Save backups**, press **Restore** beside a backup from
  before that apply (press it twice).

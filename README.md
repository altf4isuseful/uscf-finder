# Tillybob

A single-player 3D story game about a stickman, his clone, and a lot of fractions.

## Run it

```
python3 tillybob.py --open
```

That serves the game at http://localhost:8000 and turns on the **Python engine**. The HUD badge (top right) says which engine is active.
Three.js loads from a CDN, so you need an internet connection the first time.

If you only open `index.html` (or play the hosted copy), everything still works. The same fraction and cutscene logic runs in a built-in JavaScript copy, and the badge says "JS engine (offline)".

## Files

| File | What it does |
| --- | --- |
| `index.html` | The whole game: Three.js world, collision, borders, inventory, building, cutscenes, boss fight |
| `tillybob.py` | Python server. Generates fraction problems with `fractions.Fraction`, builds ordering puzzles, and picks stat-based cutscene and ending text |

## Controls

| Key | Action |
| --- | --- |
| WASD | Move |
| Arrow keys left/right, or drag | Turn the camera |
| E | Talk, open locks, chop and mine, solve a spider cage |
| 1 to 4 | Select sword, wood, stone, glass |
| B / X | Place / remove a block (stack up to 3 high) |
| G | Rally or dismiss a squad. Each squad member crosses out a wrong answer |
| H | Eat bread (heal, cure zombification), or share it with a nearby villager |
| Space | Swing sword |
| Shift | Dash (brief invulnerability) |

Touch devices get an on-screen stick and buttons.

## Story

1. Tillybob clones himself. The clone walks off.
2. A child, Pip, says spider people took his parents.
3. Spiders are floating cages. Solve the fraction on each to break it. Order fractions smallest to greatest to open the lock on the parents' cage.
4. The fence falls and you get free range. Three camps hold more villagers.
5. Gather wood and stone, build homes, rally a squad, craft a Crystal Sword at the Forge.
6. Fight your clone in the arena. Dodge function waves (plotted curves with a gap), red spots, and green mist that zombifies you. Stay out of the lava.
7. After the fight, a cutscene: your clone pushes you to the lava edge, and you throw him in first.

Cutscenes and the ending change with settlement joy, villagers freed, squad vs solo kills, accuracy, blocks placed, and whether you were zombified or fell.

## Educational content

Add and subtract fractions (like and unlike denominators), simplify, fraction of a number, multiply, compare, and ordering by size. Difficulty rises every four solved cages. Wrong answers get a worked solution.

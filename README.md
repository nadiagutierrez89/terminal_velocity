# Terminal Velocity

<video autoplay loop muted playsinline src="https://github.com/user-attachments/assets/a38df482-3dc2-4c78-a26f-5a1b38e84169" width=500></video>

A small game for a PyCamp. Build your own bot, play against bots from other people :)

# Game rules

The rules are pretty simple:

### Earning space credits

- Each player controls a spaceship, and spawns at the home base in the center of the map.
- There are asteroids all over the map, players want to mine them for resources.
- To mine an asteroid you fly to its position. Your spaceship will automatically pick it up. Then 
  you fly back to the home base, where it's automatically delivered.
- When you deliver it at the base it's mined for resources and you get credits!
- If you want to get risky, you can also hunt other spaceships! Destroying an opponent gets you 
  10% of their current credits.
- The home base is a sanctuary, spaceships can't fight while inside it.

### "ALL POWER TO THE SHIELDS!"

- You can configure your spaceship's energy usage. Direct energy to the engines, shields, or lasers.
- Your ship has 3 generators that you can connect to the different systems. For instance, you could 
  use all power (3) for the shields, while leaving lasers and engines off. Or you could use 2 
  generators for the engines, 1 for the shields and 0 for the lasers. Or any other combination you 
  like.
- What is energy used for:
    - Generators used on the **engines add speed**: each generator gives you 1 tile to move per turn. 
      If you use 3 generators for the engines, you can jump up to 3 tiles away in a single turn. If 
      you have no generators assigned to the engines, then you can't move!
    - **Shields reduce the chances you get hit** by enemy fire. Each generator used on the shields 
      reduces the chances of getting hit by 20%. So if you use 3 generators for the shields, you 
      have 60% less chances to get hit. If you have no generators assigned to the shields, then you 
      will get hit every time!
    - **Lasers increase the damage** you do when hitting the opponent. Each generator used on the 
      lasers increases the damage y 1 hitpoint. So if you use 3 generators for the lasers, you do 3 
      hitpoints of damage when you hit the opponent. Spaceships have 5 hitpoints in total. If you 
      don't assign any generator to the lasers, your spaceship won't attack other spaceships!

### Attacking

- Spaceships are from opposite factions and automatically attack each other when in range (except 
  when inside the home base).
- Spaceships automatically do one attack per turn to the other ships in range. The damage and hit
  chances depend on how the spaceships have their lasers and shields configured.
- If a spaceship is destroyed, a new one will be deployed at the home base. But any asteroids it
  was carrying stay where it died, and can be picked up by other players.
- When a spaceship is destroyed, the attacker steals 10% of the victim's credits. Pirating is fun!

### Cargo bay

- You can carry up to 2 asteroids in your cargo bay. 
- All of them get delivered at once if you reach the home base.
- **Asteroyds slow you down!** Each asteroid reduces your speed in 1. Compensate for them by 
  diverting more power to the engines. Be careful though, you might become more vulnerable when
  carrying valuable cargo!

# Installation and running the game

0. Install UV: https://docs.astral.sh/uv/getting-started/installation/

1. Clone this repo: `git clone https://github.com/fisadev/terminal_velocity.git`

2. Run a sample game with: `uv run play.py --players Alice:randomaniac,Bob:random_aggressor`

# Building your own bot

To make your own bot create a new file inside the "bots" folder, named after your bot.
For instance: "smarty_bot.py"

Inside the file define a "BotLogic" class for your bot, like this, and follow the instructions in
the docstrings to implement your logic :)

```python
class BotLogic:
    def initialize(self, map_radius, players, turns, home_base_positions):
        """
        Here you can prepare your bot for the game.
        Use it to initialize variables, prepare strategies, etc.
        You can keep all the attributes you like in `self`.
        """
        ...

    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board):
        """
        Here you write the logic of your bot.
        On each turn the game will call this function of your bot, giving you all the info about
        your current status in the game, and your bot should return what it wants to do during this
        turn.
        If your bot returns an action, the game will try to run that action (might be ignored if
        you ask for something impossible!). If your bot returns None, then it does nothing on this
        turn.
        """
        ...
```

The **turn()** method is where the magic of your bot happens!

### Inputs:

For the initialize() method:
- map_radius: the radius of the map. The home base is at position (0, 0). The map extends to -map_size 
  and +map_size in both axes.
- players: the list of player names
- turns: the number of turns the game will last
- home_base_positions: the set of positions that the base covers

For the turn() method:
- turn_number: the number of the current turn, starting at 0
- hp: how many hitpoints your spaceship has left
- ship_number: every time your ship is destroyed and a new one is created, this number will increment. 
  This lets you know if you're dying too much :)
- cargo: how many asteroids you are currently carrying
- position: your current position in space (x, y)
- power_distribution: a dictionary letting you know your current power configuration, like this:

```python
    {
        "engines": 2,  # power assigned to the engines
        "shields": 1,  # power assigned to the shields
        "lasers": 0,  # power assigned to the lasers
    }
```

- radar_contacts: a dictionary of stuff your radar sees around you, like this:

```python
    {
        (2, 4): "asteroid",
        (-3, 8): "asteroid",
        (-3, 10): "asteroid",
        (5, 6): "spaceship",  # you don't know anything else about them, just their position. It's a radar, not a crystal ball.
        (1, 2): "home_base",
        (1, 3): "home_base",  # the home base spans multiple cells
        (2, 2): "home_base",
    }
```
- leader_board: a dictionary with the names of the players and how much credits they have so far.

### Outputs:

You need to return a valid action. Valid actions are:

Moving: 
```python
    return "fly_to", (x, y)
```

This tells the game that you want to fly towards that position. If you have enough engine
power, you will. If you don't have enough engine power, your engines overheat and you don't
move at all.

Reconfiguring your ship power: 
```python
    return "power_to", {"engines": 2, "shields": 1, "lasers": 0}
```
This tells the game that you want to reconfigure your power distribution. If the new
distribution is valid, it gets applied. If it isn't, it fails to apply and you keep your
old configuration.

Once you have implemented your bot, you can start using it to play games, like this:

```bash
uv run play.py --players Alice:randomaniac,Bob:random_aggressor,MyName:my_bot
```

You can even use multiple copies of your bot at once, like this:

```bash
uv run play.py --players Alice:my_bot,Bob:my_bot,Charlie:my_bot
```

### Useful things you can use in your bot

You can import all of these things to use them in your bot:

```python
from tv.game import (
    ENGINES, SHIELDS, LASERS,  # names of the powered systems
    FLY_TO, POWER_TO,  # action names
    MAX_CARGO, MAX_HP, MAX_POWER,  # game limits
    HOME_BASE, ASTEROID, SPACESHIP,  # radar contact types
    # simple class to work with positions, with x,y attributes and some of useful methods 
    # like `distance_to(another_position)` and `positions_in_range(some_distance)`
    Position,
)
```

All the positions the game gives you in the inputs (the spaceship position, the keys in the radar 
contacts dict, etc) are instances of `Position`.

# Game options

The game allows you to configure a few things with optional command arguments. 
Check them out with:

```bash
uv run play.py --help
```

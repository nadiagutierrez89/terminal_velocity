import random

from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, RADAR_RADIUS


class BotLogic:
    """
    A bot that just moves randomly trying to find asteroids, and runs home when it finds one.
    """
    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        """
        This bot doesn't need to initialize anything except using a custom icon.
        """
        self.icon = "<>"
        self.map_radius = map_radius
        self.players = players
        self.player_name         = player_name

        self.turns = turns
        self.home_base_positions = home_base_positions
        self.map = {
            Position(i, j): ('empty', -1)
            for i in range(-map_radius, map_radius+1)
            for j in range(-map_radius, map_radius+1)
        }
        self.hp = 5
        self.turn_number = 0
        self.ship_number = 1
        self.cargo = 0
        self.position = Position(-1000, -1000)
        self.power_distribution = { ENGINES: 1, SHIELDS: 1, LASERS: 1 }
        self.radar_contacts = []
        self.leader_board = { player: 0 for player in players }

    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board):
        """
        This bot looks for asteroids, and runs home when it has one.
        """
        # speed is life
        desired_distribution = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_distribution:
            return POWER_TO, desired_distribution

        self.power_distribution = power_distribution

        speed = power_distribution[ENGINES] - cargo

        for p in position.positions_in_range(RADAR_RADIUS):
            self.map[p] = ('empty', turn_number)
        for contact_pos, contact_type in radar_contacts.items():
            self.map[contact_pos] = (contact_type, turn_number)

        if cargo:
            # run home
            return self.fly_to(position, Position(0, 0), speed)
        else:
            closest_asteroid, _ = min(
                (
                    (position, seen)
                    for (position, (kind, seen)) in self.map.items()
                    if kind == ASTEROID
                ),
                key=lambda v: (v[0].distance_to(position), -v[1]),
                default=(None, None)
            )
            if closest_asteroid:
                return self.fly_to(position, closest_asteroid, speed)

            ## Go to the least known close place
            weirdest_place, _ = min(
                (
                    (position, seen)
                    for (position, (kind, seen)) in self.map.items()
                ),
                key=lambda v: (v[1], v[0].distance_to(position)),
                default=(None, None)
            )
            return self.fly_to(position, weirdest_place, speed)

    def fly_to(self, src, dst, speed):
        possible_positions = (
            p for p in src.positions_in_range(speed)
            if abs(p.x) <= self.map_radius and abs(p.y) <= self.map_radius
        )
        return FLY_TO, min(possible_positions, key=lambda p: p.distance_to(dst))


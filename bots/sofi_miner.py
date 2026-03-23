import math
import random
import logging

logger = logging.getLogger(__name__)

from tv.game import (
    ENGINES, SHIELDS, LASERS,  # names of the powered systems
    FLY_TO, POWER_TO,  # action names
    MAX_CARGO, MAX_HP, MAX_POWER, ATTACK_RADIUS,  # game limits
    HOME_BASE, ASTEROID, SPACESHIP,  # radar contact types
    Position,
)

def iconization(f):
    def wrap(self, *args, **kwargs):
        action, metadata = f(self, *args, **kwargs)

        if action == POWER_TO:
            engines = metadata[ENGINES]
            lasers = metadata[LASERS]

        else:
            engines = kwargs["power_distribution"][ENGINES]
            lasers = kwargs["power_distribution"][LASERS]

        self.icon = f"{engines}{lasers}"

        return action, metadata

    return wrap



class State:

    def __init__(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board, map_radius):
        self.turn_number = turn_number
        self.hp = hp
        self.ship_number = ship_number
        self.cargo = cargo
        self.position = position
        self.power_distribution = power_distribution
        self.radar_contacts = radar_contacts
        self.leader_board = leader_board
        self.map_radius = map_radius

        self.speed = power_distribution[ENGINES] - cargo

        self.positions_in_range = set()

        for x, y in position.positions_in_range(self.speed):
            if abs(x) > map_radius or abs(y) > map_radius:
                continue
            self.positions_in_range.add(Position(x, y))


class BotLogic:
    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        self.player_name = player_name
        self.map_radius = map_radius
        self.players = players
        self.turns = turns
        self.home_base_positions = home_base_positions

        self.positions_without_asteroids_on_sight = set()

    def get_nearest_position_and_distance_from_points(self, position, points_to_go):
        nearest_position = None
        nearest_distance = None

        for point in points_to_go:
            distance = position.distance_to(point)

            if not nearest_position or distance < nearest_distance:
                nearest_position = point
                nearest_distance = distance

        return nearest_position, nearest_distance

    def nearest_asteroid(self, state):
        """
        If there is an asteroid in range, fly to the asteroid
        """
        asteroid_positions = [
            asteroid_position
            for asteroid_position, contact
            in state.radar_contacts.items()
            if contact == ASTEROID
        ]

        if not asteroid_positions:
            return None

        return self.get_nearest_position_and_distance_from_points(state.position, asteroid_positions)

    def go_to_position(self, postion_to_go, state):
        position_distance = math.ceil(state.position.distance_to(postion_to_go))
        if postion_to_go in state.positions_in_range:
            return FLY_TO, postion_to_go

        # if not reacheable, maximize engines
        if state.power_distribution[ENGINES] < MAX_POWER:
            optimal_engines_power = min(position_distance + state.cargo, MAX_POWER)

            # maybe power is enough to add a laser
            laser_power = MAX_POWER - optimal_engines_power

            return self.power_action(engines=optimal_engines_power, lasers=laser_power, shields=0)

        closest_position_to_asteroid = min(state.positions_in_range, key=lambda p: p.distance_to(postion_to_go))

        return FLY_TO, closest_position_to_asteroid

    def go_to_mine(self, state):
        nearest_asteroid = self.nearest_asteroid(state)
        if nearest_asteroid:
            asteroid_position, _ = nearest_asteroid
            return self.go_to_position(asteroid_position, state)

        # no asteroid on sight, fly random (avoid ships and base)
        self.positions_without_asteroids_on_sight.add(state.position)

        avoid_positions = set(state.radar_contacts.keys())
        possible_fly_positions = list(state.positions_in_range - avoid_positions - self.positions_without_asteroids_on_sight)

        if not possible_fly_positions:
            return self.power_action(engines=MAX_POWER, shields=0, lasers=0)

        return FLY_TO, random.choice(possible_fly_positions)

    def go_to_base(self, state):
        base_on_sight = [
            position
            for position, contact
            in state.radar_contacts.items()
            if contact == HOME_BASE
        ]

        if not base_on_sight:
            # no base on sight, fly to the center of the map
            base = Position(0, 0)
            return self.go_to_position(base, state)

        position, _ =  self.get_nearest_position_and_distance_from_points(state.position, base_on_sight)

        return self.go_to_position(position, state)

    @staticmethod
    def power_action(engines, shields, lasers):
        return POWER_TO, {ENGINES: int(engines), SHIELDS: int(shields), LASERS: int(lasers)}

    @iconization
    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board):
        state = State(turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board, self.map_radius)

        if state.cargo:
            self.mode = "cc"
            return self.go_to_base(state)

        self.mode = "mm"

        return self.go_to_mine(state)

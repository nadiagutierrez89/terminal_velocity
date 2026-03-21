import random

from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID


class BotLogic:
    """
    A bot that just moves randomly trying to find asteroids, and runs home when it finds one.
    """
    def initialize(self, map_radius, players, turns, home_base_positions):
        """
        This bot doesn't need to initialize anything.
        """
        pass

    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board):
        """
        This bot looks for asteroids, and runs home when it has one.
        """
        # speed is life
        desired_distribution = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_distribution:
            return POWER_TO, desired_distribution

        speed = power_distribution[ENGINES] - cargo

        if cargo:
            # run home
            home_base_position = Position(0, 0)
            reacheable_positions = list(position.positions_in_range(speed))
            closest_to_home = min(reacheable_positions, key=lambda p: p.distance_to(home_base_position))
            return FLY_TO, closest_to_home
        else:
            for contact_pos, contact_type in radar_contacts.items():
                if contact_type == ASTEROID:
                    # fly to the first asteroid we see
                    reacheable_positions = list(position.positions_in_range(speed))
                    closest_to_asteroid = min(reacheable_positions, key=lambda p: p.distance_to(contact_pos))
                    return FLY_TO, closest_to_asteroid
            # explore randomly
            return FLY_TO, random.choice(list(position.positions_in_range(1)))


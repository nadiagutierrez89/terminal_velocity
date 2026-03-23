import random

from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID


def get_corner(position,map_radius):
    
    if position.x>=0:
        corner_x = map_radius -1
    else:
        corner_x = - map_radius + 1
   
    if position.y>=0:
        corner_y = map_radius -1
    else:
        corner_y = - map_radius + 1
    return Position(corner_x,corner_y)
 

class BotLogic:
    """
    The idea is search for asteroids close to the home base. 
    """
    start_distribution = {ENGINES: 3, SHIELDS: 0, LASERS: 0}


    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        """
        Initializes history of last movements
        """
        self.map_radius = map_radius*2//3
        # self.corner = Position(map_radius,map_radius)
        self.player_name         = player_name
    
    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, radar_contacts, leader_board):
        """
        This bot looks for asteroids, and runs home when it has one.
        """
        if turn_number == 0:
            self.corner = get_corner(position,self.map_radius)

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
        #fly to the farthest cuadrant
        #"llegué a un borde"
        
        reacheable_positions = list(position.positions_in_range(speed))
        if position.distance_to(self.corner)< speed:
            #Choose another corner
            direction = random.choice([Position(1,-1),Position(-1,1)])
            self.corner = Position(self.corner.x* direction.x , self.corner.y*direction.y)
        closest_to_corner = min(reacheable_positions, key= lambda p: p.distance_to(self.corner))
        return FLY_TO, closest_to_corner

        # if cargo:
        #     # run home
        #     home_base_position = Position(0, 0)
        #     reacheable_positions = list(position.positions_in_range(speed))
        #     closest_to_home = min(reacheable_positions, key=lambda p: p.distance_to(home_base_position))
        #     return FLY_TO, closest_to_home
        # else:
        #     for contact_pos, contact_type in radar_contacts.items():
        #         if contact_type == ASTEROID:
        #             # fly to the first asteroid we see
        #             reacheable_positions = list(position.positions_in_range(speed))
        #             closest_to_asteroid = min(reacheable_positions, key=lambda p: p.distance_to(contact_pos))
        #             return FLY_TO, closest_to_asteroid
        #     # explore randomly
        #     return FLY_TO, random.choice(list(position.positions_in_range(1)))


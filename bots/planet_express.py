import random
from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, SPACESHIP


class BotLogic:
    """Planet_Express V1 - FIXED: Validación de ocupación y alejamiento de naves"""
    
    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        self.icon = ";x"
        self.player_name = player_name
        self.map_radius = map_radius
        self.players_list = players
        self.total_turns = turns
        self.home_base_positions = home_base_positions
        self.asteroid_positions = set()
        self.first_turn = True
    
    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, 
             radar_contacts, leader_board):
        if self.first_turn:
            self.first_turn = False
        
        # Detectar estrategia
        strategy = self._detect_strategy(turn_number, cargo, leader_board)
        
        if cargo > 0:
            return self._return_to_base_safe(position, cargo, hp, radar_contacts, power_distribution)
        elif strategy == "mixed_mode":
            return self._mixed_mode_search(position, cargo, power_distribution, radar_contacts)
        else:
            return self._search_asteroids_smart(position, hp, radar_contacts, power_distribution)
    
    def _return_to_base_safe(self, position, cargo, hp, radar_contacts, power_distribution):
        """Retornar a base validando ocupación y alejándose 3 tiles de naves"""
        
        enemies = self._get_enemies_in_radar(radar_contacts)
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        
        # Si cargo >= 2, MUST tener ENGINES 3
        if cargo >= 2:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        else:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = 3 - cargo
        speed = max(1, speed)
        
        reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
        
        # PRIORIDAD: Tocar la base Y alejarse 3 tiles de enemigos
        if enemies:
            closest_enemy = min(enemies, key=lambda e: position.distance_to(e))
            closest_dist = position.distance_to(closest_enemy)
            
            # Si hay enemigo muy cerca, alejarse 3 tiles mientras vuelves a base
            if closest_dist <= 5:
                safe_adjacent = []
                for p in reachable:
                    if not self._is_position_occupied(p, radar_contacts):
                        if p.distance_to(base_point) <= 1:  # Toca base
                            if p.distance_to(closest_enemy) >= 3:  # 3+ tiles
                                safe_adjacent.append(p)
                
                if safe_adjacent:
                    best = min(safe_adjacent, key=lambda p: p.distance_to(base_point))
                    return FLY_TO, best
                
                # Si no hay posición tocando base Y alejada, solo alejarse
                safe_moves = []
                for p in reachable:
                    if not self._is_position_occupied(p, radar_contacts):
                        if p.distance_to(closest_enemy) >= 3:
                            safe_moves.append((p, p.distance_to(base_point)))
                
                if safe_moves:
                    best = min(safe_moves, key=lambda x: x[1])[0]
                    return FLY_TO, best
        
        # Moverse normalmente hacia base sin ocupados
        safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
        if safe_reachable:
            best = min(safe_reachable, key=lambda p: p.distance_to(base_point))
            return FLY_TO, best
        
        # Fallback: cualquier posición no ocupada
        if reachable:
            for p in reachable:
                if not self._is_position_occupied(p, radar_contacts):
                    return FLY_TO, p
        
        return None
    
    def _search_asteroids_smart(self, position, hp, radar_contacts, power_distribution):
        """Buscar asteroides validando ocupación y rango"""
        
        enemies = self._get_enemies_in_radar(radar_contacts)
        asteroids = self._get_nearby_asteroids(radar_contacts)
        
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = 3
        
        # Si hay asteroide visible no ocupado, ir por él (CRÍTICO: validar rango)
        if asteroids:
            for asteroid in sorted(asteroids, key=lambda a: position.distance_to(a)):
                if not self._is_position_occupied(asteroid, radar_contacts) and self._is_within_range(position, asteroid, speed):
                    return FLY_TO, asteroid
        
        # Sino, explorar hacia esquina segura FIJA (deterministic)
        if speed > 0:
            # Elegir esquina más cercana como destino fijo
            if not hasattr(self, 'exploration_target'):
                corners = [
                    Position(-self.map_radius, -self.map_radius),
                    Position(-self.map_radius, self.map_radius),
                    Position(self.map_radius, -self.map_radius),
                    Position(self.map_radius, self.map_radius),
                ]
                self.exploration_target = min(corners, key=lambda c: position.distance_to(c))
            
            reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
            safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
            
            if safe_reachable:
                # Elegir punto más CERCANO a la esquina destino
                target = min(safe_reachable, key=lambda p: p.distance_to(self.exploration_target))
                return FLY_TO, target
        
        return None
    
    def _get_nearby_asteroids(self, radar_contacts):
        asteroids = set()
        for pos, obj_type in radar_contacts.items():
            if obj_type == ASTEROID:
                asteroids.add(pos)
                self.asteroid_positions.add(pos)
        return asteroids
    
    def _get_enemies_in_radar(self, radar_contacts):
        enemies = set()
        for pos, obj_type in radar_contacts.items():
            if obj_type == SPACESHIP:
                enemies.add(pos)
        return enemies
    
    def _is_position_occupied(self, target_pos, radar_contacts):
        """Verificar si una posición está ocupada por otro jugador"""
        for pos, obj_type in radar_contacts.items():
            if obj_type == SPACESHIP and pos == target_pos:
                return True
        return False    
    def _is_position_valid(self, pos):
        """CRÍTICO: Evitar límites del mapa Y 1 posición adentro del límite"""
        min_valid = -self.map_radius + 2
        max_valid = self.map_radius - 2
        return min_valid <= pos.x <= max_valid and min_valid <= pos.y <= max_valid
    
    def _is_within_range(self, from_pos, to_pos, speed):
        """CRÍTICO: Validar que destino está alcanzable con el speed actual"""
        distance = from_pos.distance_to(to_pos)
        return distance <= speed and distance > 0
    
    def _mixed_mode_search(self, position, cargo, power_distribution, radar_contacts):
        """V1 No tiene defensa, pero respeta modo mixto"""
        # V1 siempre busca con ENGINES 3
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = 3
        asteroids = self._get_nearby_asteroids(radar_contacts)
        
        if asteroids:
            for asteroid in sorted(asteroids, key=lambda a: position.distance_to(a)):
                if not self._is_position_occupied(asteroid, radar_contacts):
                    return FLY_TO, asteroid
        
        if speed > 0:
            # FASE 3: Exploración hacia esquina segura FIJA (deterministic)
            if not hasattr(self, 'exploration_target'):
                self.exploration_target = min(self.corners, key=lambda c: position.distance_to(c))
            
            reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
            safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
            
            if safe_reachable:
                target = min(safe_reachable, key=lambda p: p.distance_to(self.exploration_target))
                return FLY_TO, target
        
        return None
    
    def _detect_strategy(self, turn_number, cargo, leader_board):
        """Detectar qué estrategia usar según situación del juego"""
        
        # Estrategia: Modo mixto (desventaja económica)
        my_money = leader_board.get(self.player_name, 0)
        other_money = [money for player, money in leader_board.items() if player != self.player_name]
        if len(other_money) > 0:
            num_rich = sum(1 for m in other_money if m > 1000)
            if num_rich > len(other_money) / 2 and my_money < 1000:
                return "mixed_mode"
        
        return "normal"
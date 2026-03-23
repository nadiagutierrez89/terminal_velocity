import random
from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, SPACESHIP


class BotLogic:
    """Planet_Express V2 - FIXED: Defensa + Validación ocupación + Alejamiento"""
    
    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        self.icon = ":D"
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
        
        # Detectar estrategia según situación
        strategy = self._detect_strategy(turn_number, cargo, leader_board)
        
        if strategy == "defend_win":
            # Defender ganancia: quedarse en base con LASERS 3
            return self._defend_base_strategy(position, power_distribution, radar_contacts)
        elif strategy == "mixed_mode":
            # Modo mixto: ENGINES 2 + LASERS 1, buscar asteroides sin evitar enemigos
            return self._mixed_mode_search(position, cargo, power_distribution, radar_contacts)
        elif cargo > 0:
            # Retornar a base normal
            return self._return_to_base_safe(position, cargo, hp, radar_contacts, power_distribution)
        else:
            # Buscar asteroides normalmente
            return self._search_asteroids_safe(position, power_distribution, radar_contacts)
    
    def _return_to_base_safe(self, position, cargo, hp, radar_contacts, power_distribution):
        """Retornar a base con DEFENSA DINÁMICA validando ocupación"""
        
        enemies = self._get_enemies_in_radar(radar_contacts)
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        in_base = self._get_distance_to_base(position) <= 1
        
        # Si cargo >= 2, MUST tener ENGINES 3 (velocidad requerida)
        if cargo >= 2:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        elif in_base:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        else:
            if enemies:
                closest_enemy_dist = min((position.distance_to(e) for e in enemies), default=999)
                if hp <= 2:
                    desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
                elif hp <= 3 and closest_enemy_dist <= 2:
                    desired_power = {ENGINES: 2, SHIELDS: 1, LASERS: 0}
                elif closest_enemy_dist <= 1:
                    desired_power = {ENGINES: 2, SHIELDS: 1, LASERS: 0}
                else:
                    desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
            else:
                desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = desired_power[ENGINES] - cargo
        speed = max(1, speed)
        reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
        
        # PRIORIDAD: Tocar base Y alejarse 3 tiles de enemigos
        if enemies:
            closest_enemy = min(enemies, key=lambda e: position.distance_to(e))
            closest_dist = position.distance_to(closest_enemy)
            
            if closest_dist <= 5:
                safe_adjacent = []
                for p in reachable:
                    if not self._is_position_occupied(p, radar_contacts):
                        if p.distance_to(base_point) <= 1 and p.distance_to(closest_enemy) >= 3:
                            safe_adjacent.append(p)
                
                if safe_adjacent:
                    return FLY_TO, min(safe_adjacent, key=lambda p: p.distance_to(base_point))
                
                safe_moves = []
                for p in reachable:
                    if not self._is_position_occupied(p, radar_contacts):
                        if p.distance_to(closest_enemy) >= 3:
                            safe_moves.append((p, p.distance_to(base_point)))
                
                if safe_moves:
                    return FLY_TO, min(safe_moves, key=lambda x: x[1])[0]
        
        # Moverse normalmente hacia base sin ocupados
        safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
        if safe_reachable:
            return FLY_TO, min(safe_reachable, key=lambda p: p.distance_to(base_point))
        
        if reachable:
            for p in reachable:
                if not self._is_position_occupied(p, radar_contacts):
                    return FLY_TO, p
        
        return None
    
    def _search_asteroids_safe(self, position, power_distribution, radar_contacts):
        """Buscar asteroides sin contraataque"""
        
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = 3
        asteroids = self._get_nearby_asteroids(radar_contacts)
        
        if asteroids:
            for asteroid in sorted(asteroids, key=lambda a: position.distance_to(a)):
                # CRÍTICO: Validar que asteroide está en rango alcanzable
                if not self._is_position_occupied(asteroid, radar_contacts) and self._is_within_range(position, asteroid, speed):
                    return FLY_TO, asteroid
        
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
    
    def _mixed_mode_search(self, position, cargo, power_distribution, radar_contacts):
        """Modo mixto: ENGINES 2 + LASERS 1, buscar asteroides SIN evitar enemigos"""
        
        desired_power = {ENGINES: 2, SHIELDS: 0, LASERS: 1}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        # Si cargo >= 2, volver a ENGINES 3
        if cargo >= 2:
            return self._return_to_base_safe(position, cargo, 3, radar_contacts, power_distribution)
        
        speed = desired_power[ENGINES] - cargo
        speed = max(1, speed)
        asteroids = self._get_nearby_asteroids(radar_contacts)
        
        if asteroids:
            for asteroid in sorted(asteroids, key=lambda a: position.distance_to(a)):
                # CRÍTICO: Validar que asteroide está en rango alcanzable
                if not self._is_position_occupied(asteroid, radar_contacts) and self._is_within_range(position, asteroid, speed):
                    return FLY_TO, asteroid
        
        # Si no hay asteroides, explorar SIN evitar enemigos (pero si evitar ocupadas)
        if speed > 0:
            # FASE 3: Exploración hacia esquina segura FIJA (deterministic)
            if not hasattr(self, 'exploration_target'):
                self.exploration_target = min(self.corners, key=lambda c: position.distance_to(c))
            
            reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
            reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
            
            if reachable:
                target = min(reachable, key=lambda p: p.distance_to(self.exploration_target))
                return FLY_TO, target
        
        return None
    
    def _defend_base_strategy(self, position, power_distribution, radar_contacts):
        """Modo defensa: quedarse en base con LASERS 3"""
        
        desired_power = {ENGINES: 0, SHIELDS: 0, LASERS: 3}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        # Buscar punto de base más defensivo (con más espacios de ataque)
        best_base_pos = self._find_best_defense_position()
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        
        if position.distance_to(base_point) > 1:
            reachable = [p for p in position.positions_in_range(1) if self._is_position_valid(p)]
            safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
            
            if safe_reachable:
                closest = min(safe_reachable, key=lambda p: p.distance_to(base_point))
                return FLY_TO, closest
        
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
    
    def _get_distance_to_base(self, position):
        return min(position.distance_to(p) for p in self.home_base_positions)
    
    def _is_position_occupied(self, target_pos, radar_contacts):
        """Verificar si una posición está ocupada"""
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
    
    def _detect_strategy(self, turn_number, cargo, leader_board):
        """Detectar qué estrategia usar según situación del juego"""
        
        # Estrategia 1: Defender ganancia
        turns_remaining = self.total_turns - turn_number
        if turns_remaining < 4:
            my_money = leader_board.get(self.player_name, 0)
            # Calcular dinero promedio de otros jugadores
            other_money = [money for player, money in leader_board.items() if player != self.player_name]
            if other_money:
                avg_other = sum(other_money) / len(other_money)
                if my_money > avg_other + 2000:
                    return "defend_win"
        
        # Estrategia 2: Modo mixto (desventaja económica)
        my_money = leader_board.get(self.player_name, 0)
        other_money = [money for player, money in leader_board.items() if player != self.player_name]
        if len(other_money) > 0:
            num_rich = sum(1 for m in other_money if m > 1000)
            if num_rich > len(other_money) / 2 and my_money < 1000:
                return "mixed_mode"
        
        return "normal"
    
    def _find_best_defense_position(self):
        """Encontrar posición de base más defensiva"""
        # Por ahora, retornar primer punto de base (mejorable con análisis de espacio)
        return self.home_base_positions[0] if self.home_base_positions else Position(0, 0)

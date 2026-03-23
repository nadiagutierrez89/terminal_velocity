import random
from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, SPACESHIP


class BotLogic:
    """
    Planet_Express Bot v3: Defensa V2 + Búsqueda inteligente mejorada
    
    Mejoras en esta versión:
    - Defensa perfecta de V2 (invulnerable)
    - En la base: ENGINES 3 (no interrumpido por otras naves)
    - Búsqueda inteligente con memoria de asteroides
    - Lógica de caminos bloqueados
    - Manejo especial del centro (0,0)
    """
    
    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        """Inicializar bot con memoria de juego"""
        self.icon = ":3"
        self.player_name = player_name
        self.map_radius = map_radius
        self.players_list = players
        self.total_turns = turns
        self.home_base_positions = home_base_positions
        
        # Memoria de asteroides encontrados con posición y turno
        self.known_asteroids = {}  # {Position: turn_found}
        self.initial_spawn_position = None
        self.first_turn = True
        
        # Sistema de 6 cuadrantes para búsqueda (3 verticals x 2 horizontales)
        self.quadrants = [
            Position(-map_radius, map_radius),   # Arriba-izquierda
            Position(0, map_radius),             # Arriba-medio
            Position(map_radius, map_radius),    # Arriba-derecha
            Position(-map_radius, -map_radius),  # Abajo-izquierda
            Position(0, -map_radius),            # Abajo-medio
            Position(map_radius, -map_radius),   # Abajo-derecha
        ]
        self.turns_searching = 0
    
    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution, 
             radar_contacts, leader_board):
        """Logica principal del bot"""
        
        if self.first_turn:
            self.first_turn = False
        
        # Actualizar asteroides conocidos con nuevos descubrimientos Y remover desaparecidos
        self._update_known_asteroids(radar_contacts, turn_number)
        
        # Resetear contador de turnos si volvemos con cargo (salimos de exploración)
        if cargo > 0 and self.turns_searching > 0:
            self.turns_searching = 0
        
        # Si volvi a la base o me resucitaron, revisar si cambiar de cuadrante
        in_base = self._get_distance_to_base(position) <= 1
        if cargo == 0 and in_base and hasattr(self, 'exploration_target'):
            if self._should_change_quadrant(position, radar_contacts):
                self._select_new_quadrant(position)
        
        # Detectar estrategia segun situacion
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
            # Buscar asteroides con memoria
            return self._search_asteroids_smart(position, power_distribution, radar_contacts)
    
    # ==================== RETORNO A BASE CON DEFENSA ====================
    
    def _return_to_base_safe(self, position, cargo, hp, radar_contacts, power_distribution):
        """Retornar a base de forma segura con defensa dinámica"""
        
        # Detectar enemigos cercanos
        enemies = self._get_enemies_in_radar(radar_contacts)
        distance_to_base = self._get_distance_to_base(position)
        
        # En la base: ENGINES siempre en 3 (no afectado por otras naves)
        in_base = distance_to_base <= 1
        
        # Si cargo >= 2, MUST tener ENGINES 3 (velocidad requerida)
        if cargo >= 2:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        elif in_base:
            # SIEMPRE ENGINES 3 en la base
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        else:
            # DEFENSA DINÁMICA según situación
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
        
        # Cambiar potencia si es diferente
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        # Calcular velocidad alcanzable
        speed = desired_power[ENGINES] - cargo
        speed = max(1, speed)
        
        # Encontrar punto base más cercano
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        
        # Moverse hacia base
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
    
    # ==================== BÚSQUEDA INTELIGENTE DE ASTEROIDES ====================
    
    def _search_asteroids_smart(self, position, power_distribution, radar_contacts):
        """Búsqueda inteligente con memoria de asteroides (sin contraataque)"""
        
        asteroids_in_radar = self._get_nearby_asteroids(radar_contacts)
        
        # Asegurar potencia de minería
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        
        speed = 3  # Sin cargo cuando busca asteroides
        self.turns_searching += 1  # Incrementar contador de turnos buscando
        
        # FASE 1: Si hay asteroides en radar actual, ir por ellos
        if asteroids_in_radar:
            self.turns_searching = 0  # Reset si encontramos algo
            for asteroid in sorted(asteroids_in_radar, key=lambda a: position.distance_to(a)):
                # CRÍTICO: Validar que asteroide está en rango
                if not self._is_position_occupied(asteroid, radar_contacts) and self._is_within_range(position, asteroid, speed):
                    return FLY_TO, asteroid
        
        # FASE 2: Buscar asteroides conocidos cercanos (< 6 movimientos desde posición actual)
        nearby_known_asteroids = self._get_nearby_known_asteroids(position, max_distance=6)
        
        if nearby_known_asteroids:
            for asteroid_pos in nearby_known_asteroids:
                # CRÍTICO: Validar rango
                if not self._is_position_occupied(asteroid_pos, radar_contacts) and self._is_within_range(position, asteroid_pos, speed):
                    return FLY_TO, asteroid_pos
        
        # FASE 3: Exploración hacia cuadrante seguro FIJO (deterministic)
        # Elegir cuadrante más cercano como destino fijo
        if not hasattr(self, 'exploration_target'):
            self.exploration_target = min(self.quadrants, key=lambda q: position.distance_to(q))
        
        reachable = [p for p in position.positions_in_range(speed) if self._is_position_valid(p)]
        safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
        
        if safe_reachable:
            # Elegir punto más CERCANO al cuadrante destino (no el más lejano random)
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
        
        asteroids_in_radar = self._get_nearby_asteroids(radar_contacts)
        
        if asteroids_in_radar:
            for asteroid in sorted(asteroids_in_radar, key=lambda a: position.distance_to(a)):
                # CRÍTICO: Validar que asteroide está en rango alcanzable
                if not self._is_position_occupied(asteroid, radar_contacts) and self._is_within_range(position, asteroid, speed):
                    return FLY_TO, asteroid
        
        # Buscar conocidos
        nearby_known_asteroids = self._get_nearby_known_asteroids(position, max_distance=4)
        if nearby_known_asteroids:
            for asteroid_pos in nearby_known_asteroids:
                # CRÍTICO: Validar rango
                if not self._is_position_occupied(asteroid_pos, radar_contacts) and self._is_within_range(position, asteroid_pos, speed):
                    return FLY_TO, asteroid_pos
        
        # Si no hay asteroides, explorar SIN evitar enemigos
        if speed > 0:
            # FASE 3: Exploración hacia cuadrante seguro FIJO (deterministic)
            if not hasattr(self, 'exploration_target'):
                self.exploration_target = min(self.quadrants, key=lambda q: position.distance_to(q))
            
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
        
        # Buscar punto de base más defensivo
        best_base_pos = self._find_best_defense_position()
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        
        if position.distance_to(base_point) > 1:
            reachable = [p for p in position.positions_in_range(1) if self._is_position_valid(p)]
            safe_reachable = [p for p in reachable if not self._is_position_occupied(p, radar_contacts)]
            
            if safe_reachable:
                closest = min(safe_reachable, key=lambda p: p.distance_to(base_point))
                return FLY_TO, closest
        
        return None
    
    # ==================== HELPERS ====================
    
    def _get_nearby_asteroids(self, radar_contacts):
        """Obtener asteroides cercanos desde radar actual"""
        asteroids = set()
        for pos, obj_type in radar_contacts.items():
            if obj_type == ASTEROID:
                asteroids.add(pos)
        return asteroids
    
    def _get_enemies_in_radar(self, radar_contacts):
        """Obtener naves enemigas desde radar"""
        enemies = set()
        for pos, obj_type in radar_contacts.items():
            if obj_type == SPACESHIP:
                enemies.add(pos)
        return enemies
    
    def _get_distance_to_base(self, position):
        """Obtener distancia mínima a cualquier punto de la base"""
        return min(position.distance_to(p) for p in self.home_base_positions)
    
    def _update_known_asteroids(self, radar_contacts, turn_number):
        """Sincronizar memoria de asteroides con radar:
        - Agregar asteroides nuevos
        - Remover asteroides que desaparecieron (capturados o desvanecidos)
        """
        # Obtener asteroides actualmente en radar
        current_asteroids = set()
        for pos, obj_type in radar_contacts.items():
            if obj_type == ASTEROID:
                current_asteroids.add(pos)
                # Agregar si es nuevo
                if pos not in self.known_asteroids:
                    self.known_asteroids[pos] = turn_number
        
        # Remover asteroides que ya no existen (capturados o desvanecidos)
        forgotten = set()
        for asteroid_pos in list(self.known_asteroids.keys()):
            if asteroid_pos not in current_asteroids:
                # Si fue un asteroide conocido y ya no está, fue capturado/desvanecido
                forgotten.add(asteroid_pos)
                del self.known_asteroids[asteroid_pos]
    
    def _get_nearby_known_asteroids(self, position, max_distance=6):
        """
        Obtener asteroides conocidos cercanos (dentro de max_distance movimientos).
        Retorna lista ordenada por distancia.
        """
        nearby = []
        for asteroid_pos in self.known_asteroids.keys():
            dist = position.distance_to(asteroid_pos)
            if dist <= max_distance and dist > 0:
                nearby.append(asteroid_pos)
        
        # Ordenar por distancia
        nearby.sort(key=lambda a: position.distance_to(a))
        return nearby
    
    def _should_change_quadrant(self, position, radar_contacts):
        """Detectar si debo cambiar de cuadrante.
        Devuelve True SOLO si:
        1. No hay asteroides conocidos a menos de 6 movimientos del cuadrante actual
        2. Ya he explorado este cuadrante (he visto posiciones a mi alrededor)
        """
        if not hasattr(self, 'exploration_target'):
            return False
        
        # Verificar asteroides conocidos cercanos al cuadrante ACTUAL
        asteroids_near_quadrant = self._get_nearby_known_asteroids(self.exploration_target, max_distance=6)
        
        # Si hay asteroides cercanos, mantener el mismo cuadrante
        if asteroids_near_quadrant:
            return False
        
        # Verificar si ya hemos explorado este cuadrante (vimos posiciones cercanas)
        # Contar cuantos turnos llevamos en este cuadrante vs. asteroides vistos
        turns_in_quadrant = self.turns_searching
        asteroids_seen_in_quadrant = len([a for a in self.known_asteroids.keys() 
                                         if a.distance_to(self.exploration_target) <= 6])
        
        # Solo cambiar si llevamos tiempo explorando (>= 5 turnos) o ya vimos muchas posiciones
        if turns_in_quadrant >= 5 or (turns_in_quadrant >= 2 and asteroids_seen_in_quadrant == 0):
            return True
        
        return False
    
    def _select_new_quadrant(self, position):
        """Seleccionar un nuevo cuadrante diferente.
        Priorizar los cuadrantes mas cercanos a la posicion actual.
        Evitar cuadrantes donde ya hemos buscado exhaustivamente.
        """
        # Obtener cuadrantes ordenados por distancia desde posicion actual
        sorted_quadrants = sorted(self.quadrants, key=lambda q: position.distance_to(q))
        
        # Seleccionar el primer cuadrante diferente al actual
        current_quadrant = getattr(self, 'exploration_target', None)
        for quadrant in sorted_quadrants:
            if quadrant != current_quadrant:
                self.exploration_target = quadrant
                self.turns_searching = 0  # Reset contador de turnos en nuevo cuadrante
                return
        
        # Fallback: seleccionar aleatoriamente
        self.exploration_target = random.choice(self.quadrants)
        self.turns_searching = 0
    
    def _is_path_blocked(self, from_pos, to_pos, enemies):
        """
        Verificar si el camino directo a un asteroide está bloqueado por una nave.
        Considera si hay una nave en la línea de movimiento.
        """
        if not enemies:
            return False
        
        # Calcular camino aproximado (puntos entre from_pos y to_pos)
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        
        # Normalizar
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            return False
        
        # Verificar puntos intermedios
        for enemy_pos in enemies:
            # Si un enemigo está en el camino, es posible que bloquee
            enemy_dx = enemy_pos.x - from_pos.x
            enemy_dy = enemy_pos.y - from_pos.y
            enemy_dist = max(abs(enemy_dx), abs(enemy_dy))
            
            if enemy_dist < steps:
                # El enemigo está más cerca que el objetivo
                # Verificar si está en la "línea" de movimiento
                if steps > 0:
                    ratio_x = enemy_dx / steps if dx != 0 else 0
                    ratio_y = enemy_dy / steps if dy != 0 else 0
                    
                    # Si ambos ratios están entre 0 y 1, está en la línea
                    if 0 <= ratio_x <= 1 and 0 <= ratio_y <= 1:
                        return True
        
        return False
    
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
    
    def _get_positions_blocked_by_enemies(self, position, enemies, reachable):
        """Obtener posiciones agresivas que serían bloqueadas por enemigos"""
        blocked = set()
        for reachable_pos in reachable:
            if reachable_pos in enemies:
                blocked.add(reachable_pos)
        return blocked

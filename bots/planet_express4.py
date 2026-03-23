import random
from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, SPACESHIP


class BotLogic:
    """
    Planet_Express Bot v7 — Memoria de asteroides con TTL + prioridad post-entrega

    Novedades respecto a v6:
    - known_asteroids guarda {Position: turn_last_seen} y NO borra al salir del radar:
      expira solo si no se vio en los últimos ASTEROID_MEMORY_TURNS turnos.
    - Al entregar cargo (cargo pasa de >0 a 0 en base), elige el asteroide
      recordado MÁS CERCANO como memory_target para el siguiente viaje.
    - Cada turno se compara memory_target con los asteroides visibles por radar:
      si el radar tiene alguno más cerca, se descarta memory_target y se usa el radar.
    - Fases de búsqueda (en orden de prioridad):
        1. Radar: asteroide visible Y alcanzable con speed actual
        2. Radar: asteroide visible pero fuera de range → acercarse
        3. Memoria: memory_target (si existe y es más cercano que cualquier asteroid del radar)
        4. Memoria: cualquier asteroide recordado reciente más cercano que radar
        5. Waypoint: barrido normal por cuadrante
    """

    # ── Configuración (ajustable) ────────────────────────────────────────────
    WAYPOINT_STEP        = 2   # Separación entre waypoints de barrido (tiles)
    ASTEROID_MEMORY_TURNS = 10  # Turnos que una posición se considera "reciente"

    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        self.icon = ":P"
        self.player_name   = player_name
        self.map_radius    = map_radius
        self.players_list  = players
        self.total_turns   = turns
        self.home_base_positions = home_base_positions

        # Memoria de asteroides: {Position: turn_last_seen}
        # NO se borra al salir del radar — expira por TTL (ASTEROID_MEMORY_TURNS)
        self.known_asteroids = {}

        # Posiciones donde YO agarré un asteroide — excluidas de memory_target
        # Se rehabilitan solo si el radar vuelve a ver un asteroide ahí (respawn)
        self.grabbed_positions = set()

        self.first_turn  = True
        self.prev_cargo  = 0       # para detectar el momento de entrega

        # Objetivo de memoria elegido post-entrega
        self.memory_target = None  # Position | None

        # ── 6 cuadrantes con waypoints ───────────────────────────────────────
        self.quadrants      = self._build_quadrants(map_radius)
        self.quadrant_names = list(self.quadrants.keys())

        self.current_quadrant  = None
        self.waypoint_index    = 0
        self.turns_on_waypoint = 0
        self.visited_quadrants = []

        # Anti-loop
        self.HISTORY_LEN = 6
        self.pos_history = []

    # ══════════════════════════════════════════════════════════════════════════
    #  TURNO PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution,
             radar_contacts, leader_board):

        if self.first_turn:
            self.first_turn = False
            self._select_closest_quadrant(position)

        # 1. Actualizar memoria (TTL, no borrar por salir del radar)
        self._update_known_asteroids(radar_contacts, turn_number)

        # 2. Anti-loop — SOLO activo cuando no tenemos cargo
        #    Con cargo, el objetivo es la base; el "loop" es normal al acercarse esquivando naves
        if cargo == 0:
            self.pos_history.append(position)
            if len(self.pos_history) > self.HISTORY_LEN:
                self.pos_history.pop(0)
            if self._detect_position_loop():
                self._advance_waypoint(position, force_new_quadrant=True)
        else:
            self.pos_history.clear()  # resetear historial al tener cargo

        # 3. Detectar si acabamos de agarrar un asteroide (cargo pasó de 0 a >0)
        just_grabbed = self.prev_cargo == 0 and cargo > 0
        if just_grabbed:
            # Registrar posición como "consumida por mí" — no volver como memory_target
            self.grabbed_positions.add(position)
            # Borrar de la memoria inmediatamente
            self.known_asteroids.pop(position, None)
            if self.memory_target == position:
                self.memory_target = None

        # 4. Detectar momento de entrega (cargo > 0 → cargo == 0 estando en base)
        just_delivered = (
            self.prev_cargo > 0
            and cargo == 0
            and self._get_distance_to_base(position) <= 1
        )
        if just_delivered:
            self._pick_memory_target(position, radar_contacts, turn_number)

        self.prev_cargo = cargo

        # 5. Validar memory_target cada turno contra el radar (solo sin cargo)
        if cargo == 0 and self.memory_target is not None:
            self._validate_memory_target(position, radar_contacts)

        # 6. Contadores de waypoint — solo cuando buscamos (sin cargo)
        if cargo > 0:
            self.turns_on_waypoint = 0
        else:
            self.turns_on_waypoint += 1
            if self._should_advance_waypoint():
                self._advance_waypoint(position)

        # 6. Estrategia
        strategy = self._detect_strategy(turn_number, cargo, leader_board)

        if strategy == "defend_win":
            return self._defend_base_strategy(position, power_distribution, radar_contacts)
        elif strategy == "mixed_mode":
            return self._mixed_mode_search(position, cargo, power_distribution, radar_contacts)
        elif cargo > 0:
            return self._return_to_base_safe(position, cargo, hp, radar_contacts, power_distribution)
        else:
            return self._search_asteroids_smart(position, power_distribution, radar_contacts)

    # ══════════════════════════════════════════════════════════════════════════
    #  MEMORIA DE ASTEROIDES
    # ══════════════════════════════════════════════════════════════════════════

    def _update_known_asteroids(self, radar_contacts, turn_number):
        """
        - Actualiza turn_last_seen para asteroides visibles ahora.
        - Si el radar ve un asteroide en una posición que habíamos grabado,
          significa que respawneó → rehabilitar (sacar de grabbed_positions).
        - Excluye grabbed_positions del dict (no recordar lo que ya consumimos).
        - Expira entradas más antiguas que ASTEROID_MEMORY_TURNS.
        """
        for pos, obj_type in radar_contacts.items():
            if obj_type == ASTEROID:
                # Si estaba en grabbed, respawneó → rehabilitar
                if pos in self.grabbed_positions:
                    self.grabbed_positions.discard(pos)
                self.known_asteroids[pos] = turn_number

        # Expirar por TTL y limpiar grabbed del dict (por si se coló antes del grab)
        for pos in list(self.known_asteroids):
            if pos in self.grabbed_positions:
                del self.known_asteroids[pos]
                continue
            if turn_number - self.known_asteroids[pos] > self.ASTEROID_MEMORY_TURNS:
                del self.known_asteroids[pos]
                if self.memory_target == pos:
                    self.memory_target = None

    def _pick_memory_target(self, position, radar_contacts, turn_number):
        """
        Llamado justo después de entregar cargo.
        Elige el asteroide recordado más cercano, excluyendo:
        - La posición base actual (acabamos de entregar)
        - grabbed_positions (posiciones que nosotros mismos consumimos)
        Si no hay ninguno válido, memory_target = None → usa waypoints.
        """
        candidates = [
            p for p in self.known_asteroids
            if p not in self.grabbed_positions
        ]
        if not candidates:
            self.memory_target = None
            return

        candidates.sort(key=lambda p: position.distance_to(p))
        self.memory_target = candidates[0]

    def _validate_memory_target(self, position, radar_contacts):
        """
        Llamado cada turno mientras memory_target != None.
        Descarta memory_target si:
        - Ya expiró de la memoria
        - El radar tiene un asteroide MÁS CERCANO que memory_target
        """
        if self.memory_target not in self.known_asteroids:
            self.memory_target = None
            return

        asteroids_radar = self._get_nearby_asteroids(radar_contacts)
        if not asteroids_radar:
            return

        dist_target = position.distance_to(self.memory_target)
        closest_radar_dist = min(position.distance_to(a) for a in asteroids_radar)

        if closest_radar_dist < dist_target:
            # El radar tiene algo más cerca → descartar memoria, priorizar radar
            self.memory_target = None

    def _get_recent_asteroids_sorted(self, position):
        """
        Devuelve asteroides de memoria ordenados por distancia,
        solo los que aún están vigentes (TTL no expirado — ya filtrado en update).
        """
        candidates = list(self.known_asteroids.keys())
        candidates.sort(key=lambda p: position.distance_to(p))
        return candidates

    # ══════════════════════════════════════════════════════════════════════════
    #  BÚSQUEDA PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def _search_asteroids_smart(self, position, power_distribution, radar_contacts):
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = 3
        asteroids_radar = self._get_nearby_asteroids(radar_contacts)
        closest_radar_dist = min(
            (position.distance_to(a) for a in asteroids_radar), default=float('inf')
        )

        # ── FASE 1: Radar — asteroide alcanzable ahora ────────────────────────
        for ast in sorted(asteroids_radar, key=lambda a: position.distance_to(a)):
            if self._is_within_range(position, ast, speed) \
               and not self._is_position_occupied(ast, radar_contacts):
                self.turns_on_waypoint = 0
                self.memory_target = None   # llegamos por radar, limpiar memoria
                return FLY_TO, ast

        # ── FASE 2: Radar — asteroide visible pero fuera de range → acercarse ─
        if asteroids_radar:
            closest_radar = min(asteroids_radar, key=lambda a: position.distance_to(a))
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                self.turns_on_waypoint = 0
                return FLY_TO, min(free, key=lambda p: p.distance_to(closest_radar))

        # ── FASE 3: memory_target (ya validado, es más cercano que radar) ─────
        if self.memory_target is not None:
            if self._is_within_range(position, self.memory_target, speed) \
               and not self._is_position_occupied(self.memory_target, radar_contacts):
                self.turns_on_waypoint = 0
                return FLY_TO, self.memory_target
            else:
                # Acercarse al memory_target
                free = self._safe_reachable(position, speed, radar_contacts)
                if free:
                    self.turns_on_waypoint = 0
                    return FLY_TO, min(free, key=lambda p: p.distance_to(self.memory_target))

        # ── FASE 4: Memoria general — cualquier asteroide recordado más cercano
        #            que cualquier cosa del radar ────────────────────────────────
        for ast_pos in self._get_recent_asteroids_sorted(position):
            dist_mem = position.distance_to(ast_pos)
            if dist_mem >= closest_radar_dist:
                continue   # no vale la pena, radar tiene algo igual o más cerca
            if self._is_within_range(position, ast_pos, speed) \
               and not self._is_position_occupied(ast_pos, radar_contacts):
                self.turns_on_waypoint = 0
                return FLY_TO, ast_pos
            else:
                # Acercarse
                free = self._safe_reachable(position, speed, radar_contacts)
                if free:
                    self.turns_on_waypoint = 0
                    return FLY_TO, min(free, key=lambda p: p.distance_to(ast_pos))

        # ── FASE 5: Waypoint de barrido ───────────────────────────────────────
        return self._move_toward_waypoint(position, speed, radar_contacts)

    # ══════════════════════════════════════════════════════════════════════════
    #  GESTIÓN DE CUADRANTES Y WAYPOINTS
    # ══════════════════════════════════════════════════════════════════════════

    def _build_quadrants(self, r):
        step = self.WAYPOINT_STEP
        lo = -(r - 2)
        hi =  (r - 2)

        def waypoints_for(cx, cy):
            pts = []
            for dist in range(step, r, step):
                x_base = cx * dist
                y_base = cy * dist
                for dx in range(-step // 2, step // 2 + 1, max(1, step // 2)):
                    for dy in range(-step // 2, step // 2 + 1, max(1, step // 2)):
                        x = x_base + dx if cx != 0 else dx
                        y = y_base + dy if cy != 0 else dy
                        x = max(lo, min(hi, x))
                        y = max(lo, min(hi, y))
                        p = Position(x, y)
                        if p not in pts:
                            pts.append(p)
            center = Position(cx * (r - 3), cy * (r - 3))
            pts.sort(key=lambda p: p.distance_to(center))
            return pts

        return {
            "arriba_izq":   waypoints_for(-1,  1),
            "arriba_medio": waypoints_for( 0,  1),
            "arriba_der":   waypoints_for( 1,  1),
            "abajo_izq":    waypoints_for(-1, -1),
            "abajo_medio":  waypoints_for( 0, -1),
            "abajo_der":    waypoints_for( 1, -1),
        }

    def _select_closest_quadrant(self, position):
        best = min(
            self.quadrant_names,
            key=lambda n: position.distance_to(self.quadrants[n][0])
        )
        self._set_quadrant(best, waypoint_index=0)

    def _set_quadrant(self, name, waypoint_index=0):
        self.current_quadrant  = name
        self.waypoint_index    = waypoint_index
        self.turns_on_waypoint = 0
        self.visited_quadrants.append(name)
        if len(self.visited_quadrants) > 5:
            self.visited_quadrants.pop(0)
        self.pos_history.clear()

    def _current_waypoint(self):
        if self.current_quadrant is None:
            return None
        waypoints = self.quadrants[self.current_quadrant]
        idx = min(self.waypoint_index, len(waypoints) - 1)
        return waypoints[idx]

    def _should_advance_waypoint(self):
        wp = self._current_waypoint()
        if wp is None:
            return False
        nearby = [p for p in self.known_asteroids if 0 < wp.distance_to(p) <= 5]
        if self.turns_on_waypoint >= 3:
            return True
        if self.turns_on_waypoint >= 2 and not nearby:
            return True
        return False

    def _advance_waypoint(self, position, force_new_quadrant=False):
        if self.current_quadrant is None:
            self._select_closest_quadrant(position)
            return
        waypoints = self.quadrants[self.current_quadrant]
        next_idx  = self.waypoint_index + 1
        if not force_new_quadrant and next_idx < len(waypoints):
            self.waypoint_index    = next_idx
            self.turns_on_waypoint = 0
            self.pos_history.clear()
        else:
            self._select_new_quadrant(position, force=force_new_quadrant)

    def _select_new_quadrant(self, position, force=False):
        candidates = [n for n in self.quadrant_names if n != self.current_quadrant]
        not_recent = [n for n in candidates if n not in self.visited_quadrants]
        pool = not_recent if not_recent else candidates
        if not pool:
            pool = candidates
        if force:
            chosen = max(pool, key=lambda n: position.distance_to(self.quadrants[n][0]))
        else:
            chosen = min(pool, key=lambda n: position.distance_to(self.quadrants[n][0]))
        self._set_quadrant(chosen, waypoint_index=0)

    def _detect_position_loop(self):
        if len(self.pos_history) < self.HISTORY_LEN // 2:
            return False
        seen = {}
        for pos in self.pos_history:
            key = (pos.x, pos.y)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] >= 2:
                return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    #  ESTRATEGIAS
    # ══════════════════════════════════════════════════════════════════════════

    def _return_to_base_safe(self, position, cargo, hp, radar_contacts, power_distribution):
        """
        Volver a entregar cargo. Tres casos según visibilidad de la base:

        CASO A — La base NO está en el radar todavía:
            Asumir que el tile de base más cercano (por distancia conocida) está libre
            y acercarse hacia él usando _safe_reachable.

        CASO B — La base está en el radar y hay al menos un tile libre:
            Ir al tile libre más cercano. Si está en range → directo.
            Si no → acercarse por _safe_reachable hacia ese tile.

        CASO C — La base está en el radar pero TODOS sus tiles están ocupados:
            Ir hacia el tile de base más cercano que NO aparece en el radar
            (asumirlo libre). Acercarse usando _safe_reachable.

        NUNCA fly_to a una posición ocupada por otra nave.
        """
        enemies = self._get_enemies_in_radar(radar_contacts)

        # ── Potencia ─────────────────────────────────────────────────────────
        in_base = self._get_distance_to_base(position) <= 1
        if cargo >= 2 or in_base:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        elif enemies:
            closest_dist = min(position.distance_to(e) for e in enemies)
            if hp <= 2 or closest_dist > 2:
                desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
            else:
                desired_power = {ENGINES: 2, SHIELDS: 1, LASERS: 0}
        else:
            desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}

        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = max(1, desired_power[ENGINES] - cargo)

        # ── Clasificar tiles de base según visibilidad en radar ───────────────
        visible_base  = [p for p in self.home_base_positions if p in radar_contacts]
        invisible_base = [p for p in self.home_base_positions if p not in radar_contacts]

        free_visible  = [p for p in visible_base
                         if not self._is_position_occupied(p, radar_contacts)]

        # ── Elegir destino según caso ─────────────────────────────────────────
        if not visible_base:
            # CASO A: base fuera del radar → asumir libre el más cercano conocido
            target = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        elif free_visible:
            # CASO B: hay tiles visibles libres → el más cercano
            target = min(free_visible, key=lambda p: position.distance_to(p))
        else:
            # CASO C: todos los tiles visibles ocupados → ir al invisible más cercano
            if invisible_base:
                target = min(invisible_base, key=lambda p: position.distance_to(p))
            else:
                # Todos los tiles visibles y están todos ocupados, esperar un turno
                return None

        # ── Moverse hacia target ──────────────────────────────────────────────
        if self._is_within_range(position, target, speed):
            # Llegar directo (target ya es libre o asumido libre)
            return FLY_TO, target

        # Acercarse por celda libre que minimice distancia al target
        reachable = self._safe_reachable(position, speed, radar_contacts)
        if not reachable:
            return None

        # Evitar enemigos si es posible sin alejarse de la base
        if enemies:
            closest_enemy = min(enemies, key=lambda e: position.distance_to(e))
            if position.distance_to(closest_enemy) <= 5:
                safe = [p for p in reachable if p.distance_to(closest_enemy) >= 3]
                if safe:
                    return FLY_TO, min(safe, key=lambda p: p.distance_to(target))

        return FLY_TO, min(reachable, key=lambda p: p.distance_to(target))

    def _mixed_mode_search(self, position, cargo, power_distribution, radar_contacts):
        desired_power = {ENGINES: 2, SHIELDS: 0, LASERS: 1}
        if power_distribution != desired_power:
            return POWER_TO, desired_power

        if cargo >= 2:
            return self._return_to_base_safe(position, cargo, 3, radar_contacts, power_distribution)

        speed = max(1, desired_power[ENGINES] - cargo)
        asteroids_radar    = self._get_nearby_asteroids(radar_contacts)
        closest_radar_dist = min(
            (position.distance_to(a) for a in asteroids_radar), default=float('inf')
        )

        for ast in sorted(asteroids_radar, key=lambda a: position.distance_to(a)):
            if self._is_within_range(position, ast, speed) \
               and not self._is_position_occupied(ast, radar_contacts):
                return FLY_TO, ast

        if asteroids_radar:
            closest_radar = min(asteroids_radar, key=lambda a: position.distance_to(a))
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                return FLY_TO, min(free, key=lambda p: p.distance_to(closest_radar))

        for ast_pos in self._get_recent_asteroids_sorted(position):
            if position.distance_to(ast_pos) >= closest_radar_dist:
                continue
            if self._is_within_range(position, ast_pos, speed) \
               and not self._is_position_occupied(ast_pos, radar_contacts):
                return FLY_TO, ast_pos
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                return FLY_TO, min(free, key=lambda p: p.distance_to(ast_pos))

        return self._move_toward_waypoint(position, speed, radar_contacts)

    def _defend_base_strategy(self, position, power_distribution, radar_contacts):
        desired_power = {ENGINES: 0, SHIELDS: 0, LASERS: 3}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        base_point = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        if position.distance_to(base_point) > 1:
            reachable = self._safe_reachable(position, 1, radar_contacts)
            if reachable:
                return FLY_TO, min(reachable, key=lambda p: p.distance_to(base_point))
        return None

    # ══════════════════════════════════════════════════════════════════════════
    #  MOVIMIENTO
    # ══════════════════════════════════════════════════════════════════════════

    def _move_toward_waypoint(self, position, speed, radar_contacts):
        wp = self._current_waypoint()
        if wp is None:
            self._select_closest_quadrant(position)
            wp = self._current_waypoint()

        if position.distance_to(wp) <= max(1, speed // 2):
            self._advance_waypoint(position)
            wp = self._current_waypoint()

        free = self._safe_reachable(position, speed, radar_contacts)
        if not free:
            return None
        return FLY_TO, min(free, key=lambda p: p.distance_to(wp))

    # ══════════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _safe_reachable(self, position, speed, radar_contacts):
        result = []
        for p in position.positions_in_range(speed):
            if not self._is_position_valid(p):
                continue
            if self._is_position_occupied(p, radar_contacts):
                continue
            d = position.distance_to(p)
            if d == 0 or d > speed:
                continue
            result.append(p)
        return result

    def _get_nearby_asteroids(self, radar_contacts):
        return {pos for pos, t in radar_contacts.items() if t == ASTEROID}

    def _get_enemies_in_radar(self, radar_contacts):
        return {pos for pos, t in radar_contacts.items() if t == SPACESHIP}

    def _get_distance_to_base(self, position):
        return min(position.distance_to(p) for p in self.home_base_positions)

    def _is_position_occupied(self, target_pos, radar_contacts):
        return any(t == SPACESHIP and p == target_pos for p, t in radar_contacts.items())

    def _is_position_valid(self, pos):
        lo = -self.map_radius + 2
        hi =  self.map_radius - 2
        return lo <= pos.x <= hi and lo <= pos.y <= hi

    def _is_within_range(self, from_pos, to_pos, speed):
        d = from_pos.distance_to(to_pos)
        return 0 < d <= speed

    def _detect_strategy(self, turn_number, cargo, leader_board):
        turns_remaining = self.total_turns - turn_number
        my_money = leader_board.get(self.player_name, 0)
        others   = [m for p, m in leader_board.items() if p != self.player_name]

        if turns_remaining < 4 and others:
            if my_money > sum(others) / len(others) + 2000:
                return "defend_win"
        if others:
            num_rich = sum(1 for m in others if m > 1000)
            if num_rich > len(others) / 2 and my_money < 1000:
                return "mixed_mode"
        return "normal"
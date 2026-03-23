import random
from tv.game import Position, POWER_TO, FLY_TO, LASERS, ENGINES, SHIELDS, ASTEROID, SPACESHIP

MAX_MOVES_TO_ASTEROID = 3    # movimientos maximos hacia el prox asteroide recordado

class BotLogic:
    """
    Planet_Express Bot v9

    Lógica de exploración rediseñada:
    - El mapa se divide en 6 sextantes alrededor de la base.
    - Al salir de la base sin memory_target, el bot va DIRECTO al centro del
      sextante elegido (2 movimientos de speed=3 = hasta 6 tiles).
    - Si tras MAX_MOVES_IN_SEXTANT movimientos completos en ese sextante no
      encontró asteroides (radar vacío y memoria vacía del sextante), cambia
      al sextante adyacente no conocido más cercano.
    - Nunca usa waypoints de 1 tile: cada "paso de exploración" es un vuelo
      hacia el centro del sextante o hacia el sextante siguiente.
    """

    # ── Configuración ────────────────────────────────────────────────────────
    ASTEROID_MEMORY_TURNS = 10   # turnos que dura un asteroide en memoria
    MAX_MOVES_IN_SEXTANT  = 2    # movimientos sin encontrar nada → cambiar sextante
    SEXTANT_RADIUS_FACTOR = 0.6  # centro del sextante a este factor del radio

    def initialize(self, player_name, map_radius, players, turns, home_base_positions):
        self.icon = "ƤƎ"
        self.player_name         = player_name
        self.map_radius          = map_radius
        self.players_list        = players
        self.total_turns         = turns
        self.home_base_positions = home_base_positions

        # Memoria de asteroides {Position: turn_last_seen} — expira por TTL
        self.known_asteroids  = {}
        self.grabbed_positions = set()

        self.first_turn  = True
        self.prev_cargo  = 0
        self.memory_target  = None
        self.enemy_target   = None   # objetivo de caza en modo aggressor

        # ── 6 sextantes: centro de cada uno ──────────────────────────────────
        # Disposición alrededor de la base (0,0):
        #   arriba_izq  arriba_medio  arriba_der
        #   abajo_izq   abajo_medio   abajo_der
        d = max(3, int(map_radius * self.SEXTANT_RADIUS_FACTOR))
        self.sextants = {
            "arriba_izq":   Position(-d,  d),
            "arriba_medio": Position( 0,  d),
            "arriba_der":   Position( d,  d),
            "abajo_izq":    Position(-d, -d),
            "abajo_medio":  Position( 0, -d),
            "abajo_der":    Position( d, -d),
        }
        # Adyacencias de cada sextante (para elegir el siguiente)
        self.sextant_adj = {
            "arriba_izq":   ["arriba_medio", "abajo_izq"],
            "arriba_medio": ["arriba_izq",   "arriba_der"],
            "arriba_der":   ["arriba_medio", "abajo_der"],
            "abajo_izq":    ["abajo_medio",  "arriba_izq"],
            "abajo_medio":  ["abajo_izq",    "abajo_der"],
            "abajo_der":    ["abajo_medio",  "arriba_der"],
        }
        self.sextant_names   = list(self.sextants.keys())

        self.current_sextant    = None   # nombre del sextante activo
        self.moves_in_sextant   = 0      # movimientos hechos en este sextante sin encontrar nada
        self.visited_sextants   = []     # historial de visitados (últimos 5)

        # ── Expansión de radio tras vuelta completa sin asteroides ───────────
        # expansion_level 0 = radio original; +1 por cada vuelta sin agarrar nada
        self.expansion_level     = 0
        self.sextants_this_round = set()  # sextantes visitados en la vuelta actual
        self._base_d  = max(3, int(map_radius * self.SEXTANT_RADIUS_FACTOR))
        self._max_d   = map_radius - 3    # margen seguro respecto al borde

        # Anti-loop
        self.HISTORY_LEN = 4
        self.pos_history = []

    # ══════════════════════════════════════════════════════════════════════════
    #  TURNO PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def turn(self, turn_number, hp, ship_number, cargo, position, power_distribution,
             radar_contacts, leader_board):

        if self.first_turn:
            self.first_turn = False
            self._select_closest_sextant(position)

        # 1. Actualizar memoria
        self._update_known_asteroids(radar_contacts, turn_number)

        # 2. Anti-loop (solo sin cargo)
        if cargo == 0:
            self.pos_history.append(position)
            if len(self.pos_history) > self.HISTORY_LEN:
                self.pos_history.pop(0)
            if self._detect_position_loop():
                self._change_sextant(position, force=True)
        else:
            self.pos_history.clear()

        # 3. Detectar grab
        just_grabbed = self.prev_cargo == 0 and cargo > 0
        if just_grabbed:
            self.grabbed_positions.add(position)
            self.known_asteroids.pop(position, None)
            if self.memory_target == position:
                self.memory_target = None

        # 4. Detectar entrega → resetear expansión
        just_delivered = (
            self.prev_cargo > 0
            and cargo == 0
            and self._get_distance_to_base(position) <= 1
        )
        if just_delivered:
            self._pick_memory_target(position)
            # Resetear expansión: volvimos con cargo, el mapa se "reinicia"
            self.expansion_level     = 0
            self.sextants_this_round = set()

        self.prev_cargo = cargo

        # 5. Validar memory_target cada turno
        if cargo == 0 and self.memory_target is not None:
            self._validate_memory_target(position, radar_contacts)

        # 6. Estrategia
        strategy = self._detect_strategy(turn_number, cargo, leader_board, hp)
        if strategy == "defend_win":
            return self._defend_base_strategy(position, power_distribution, radar_contacts)
        elif strategy == "low_hp_defense":
            return self._low_hp_defense(position, cargo, power_distribution, radar_contacts)
        elif strategy == "aggressor":
            return self._aggressor_mode(position, cargo, hp, power_distribution, radar_contacts)
        elif strategy == "mixed_mode":
            return self._mixed_mode_search(position, cargo, power_distribution, radar_contacts)
        elif cargo > 0:
            return self._return_to_base_safe(position, cargo, hp, radar_contacts, power_distribution)
        else:
            return self._search_asteroids_smart(position, turn_number, power_distribution, radar_contacts)

    # ══════════════════════════════════════════════════════════════════════════
    #  MEMORIA DE ASTEROIDES
    # ══════════════════════════════════════════════════════════════════════════

    def _update_known_asteroids(self, radar_contacts, turn_number):
        for pos, obj_type in radar_contacts.items():
            if obj_type == ASTEROID:
                if pos in self.grabbed_positions:
                    self.grabbed_positions.discard(pos)
                self.known_asteroids[pos] = turn_number

        for pos in list(self.known_asteroids):
            if pos in self.grabbed_positions:
                del self.known_asteroids[pos]
                continue
            if turn_number - self.known_asteroids[pos] > self.ASTEROID_MEMORY_TURNS:
                del self.known_asteroids[pos]
                if self.memory_target == pos:
                    self.memory_target = None

    def _pick_memory_target(self, position):
        """Post-entrega: elegir asteroide recordado más cercano (excluye grabbed)."""
        candidates = [p for p in self.known_asteroids if p not in self.grabbed_positions]
        if not candidates:
            self.memory_target = None
            return
        candidates.sort(key=lambda p: position.distance_to(p))
        # Solo usar memoria si está a menos de 6 tiles (sino es más eficiente el sextante)
        closest = candidates[0]
        if position.distance_to(closest) <= 6:
            self.memory_target = closest
        else:
            self.memory_target = None

    def _validate_memory_target(self, position, radar_contacts):
        """Descartar memory_target si expiró o el radar tiene algo más cerca."""
        if self.memory_target not in self.known_asteroids:
            self.memory_target = None
            return
        asteroids_radar = self._get_nearby_asteroids(radar_contacts)
        if asteroids_radar:
            closest_radar_dist = min(position.distance_to(a) for a in asteroids_radar)
            if closest_radar_dist < position.distance_to(self.memory_target):
                self.memory_target = None

    # ══════════════════════════════════════════════════════════════════════════
    #  GESTIÓN DE SEXTANTES
    # ══════════════════════════════════════════════════════════════════════════

    def _select_closest_sextant(self, position):
        """Elige el sextante más cercano a la posición actual."""
        best = min(self.sextant_names,
                   key=lambda n: position.distance_to(self.sextants[n]))
        self._set_sextant(best)

    def _set_sextant(self, name):
        self.current_sextant  = name
        self.moves_in_sextant = 0
        self.visited_sextants.append(name)
        if len(self.visited_sextants) > 5:
            self.visited_sextants.pop(0)
        self.pos_history.clear()
        # Registrar en la vuelta actual
        self.sextants_this_round.add(name)
        # Vuelta completa sin encontrar nada → expandir radio
        if len(self.sextants_this_round) >= len(self.sextant_names):
            self.expansion_level    += 1
            self.sextants_this_round = set()

    def _change_sextant(self, position, force=False):
        """
        Cambia al sextante adyacente más conveniente:
        - Prioriza adyacentes sin asteroides conocidos (zona "nueva")
        - Si force=True (loop), elige el más lejano para escapar
        """
        current = self.current_sextant
        adj = self.sextant_adj.get(current, self.sextant_names)

        # Separar adyacentes en "sin asteroides conocidos" vs "con asteroides"
        def known_asteroids_near(sextant_name):
            center = self.sextants[sextant_name]
            return any(center.distance_to(p) <= self.map_radius // 2
                       for p in self.known_asteroids)

        unknown_adj = [n for n in adj if not known_asteroids_near(n)]
        known_adj   = [n for n in adj if known_asteroids_near(n)]

        # Pool: primero los no-visitados-recientemente entre los adyacentes
        pool = [n for n in (unknown_adj or adj) if n not in self.visited_sextants]
        if not pool:
            pool = unknown_adj or adj

        if force:
            chosen = max(pool, key=lambda n: position.distance_to(self.sextants[n]))
        else:
            chosen = min(pool, key=lambda n: position.distance_to(self.sextants[n]))

        self._set_sextant(chosen)

    def _sextant_has_recent_asteroids(self, sextant_name):
        """¿Hay asteroides recordados cerca del centro de este sextante?"""
        center = self.sextants[sextant_name]
        radius = self.map_radius // 2
        return any(center.distance_to(p) <= radius for p in self.known_asteroids)

    # ══════════════════════════════════════════════════════════════════════════
    #  BÚSQUEDA PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def _search_asteroids_smart(self, position, turn_number, power_distribution, radar_contacts):
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = 3
        asteroids_radar    = self._get_nearby_asteroids(radar_contacts)
        closest_radar_dist = min((position.distance_to(a) for a in asteroids_radar),
                                 default=float('inf'))

        # ── FASE 1: Asteroide en radar alcanzable ahora ───────────────────────
        for ast in sorted(asteroids_radar, key=lambda a: position.distance_to(a)):
            if self._is_within_range(position, ast, speed) \
               and not self._is_position_occupied(ast, radar_contacts):
                self.moves_in_sextant = 0
                self.memory_target = None
                return FLY_TO, ast

        # ── FASE 2: Asteroide en radar fuera de range → acercarse ─────────────
        if asteroids_radar:
            closest = min(asteroids_radar, key=lambda a: position.distance_to(a))
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                # No resetear moves_in_sextant — si no llegamos a agarrarlo,
                # el contador sigue corriendo para cambiar sextante
                return FLY_TO, min(free, key=lambda p: p.distance_to(closest))

        # ── FASE 3: memory_target ─────────────────────────────────────────────
        if self.memory_target is not None:
            moves = self._moves_to_position(position, self.memory_target, speed)

            if moves > MAX_MOVES_TO_ASTEROID:
                self.memory_target = None
            else:
                free = self._safe_reachable(position, speed, radar_contacts)
                if free:
                    if self._is_within_range(position, self.memory_target, speed) \
                    and not self._is_position_occupied(self.memory_target, radar_contacts):
                        self.moves_in_sextant = 0
                        return FLY_TO, self.memory_target
                    return FLY_TO, min(free, key=lambda p: p.distance_to(self.memory_target))

        # ── FASE 4: Memoria general — más cercana que cualquier cosa del radar ─
        for ast_pos in sorted(self.known_asteroids.keys(),
                              key=lambda p: position.distance_to(p)):
            if ast_pos in self.grabbed_positions:
                continue

            moves = self._moves_to_position(position, ast_pos, speed)
            if moves > MAX_MOVES_TO_ASTEROID:
                continue

            if position.distance_to(ast_pos) >= closest_radar_dist:
                continue
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                self.moves_in_sextant = 0
                if self._is_within_range(position, ast_pos, speed) \
                   and not self._is_position_occupied(ast_pos, radar_contacts):
                    return FLY_TO, ast_pos
                return FLY_TO, min(free, key=lambda p: p.distance_to(ast_pos))

        # ── FASE 5: Exploración por sextante ─────────────────────────────────
        return self._explore_sextant(position, speed, radar_contacts)

    def _explore_sextant(self, position, speed, radar_contacts):
        """
        Mueve hacia el centro EXPANDIDO del sextante activo.

        expansion_level 0 → centro original (SEXTANT_RADIUS_FACTOR del radio)
        expansion_level N → centro desplazado N pasos extra hacia el borde:
          - speed==3: 2 tiles hacia el borde + 1 lateral (diagonal)
          - speed==2: 2 tiles hacia el borde directo

        Tras MAX_MOVES_IN_SEXTANT movimientos sin encontrar nada → cambiar sextante.
        """
        # Contar este movimiento de exploración
        self.moves_in_sextant += 1

        # Si agotamos los movimientos permitidos → cambiar sextante
        if self.moves_in_sextant > self.MAX_MOVES_IN_SEXTANT:
            self._change_sextant(position)

        center = self._get_expanded_center(self.current_sextant, speed)

        free = self._safe_reachable(position, speed, radar_contacts)
        if not free:
            return None

        return FLY_TO, min(free, key=lambda p: p.distance_to(center))

    def _get_expanded_center(self, sextant_name, speed):
        """
        Calcula el centro del sextante ajustado por expansion_level.

        Cada nivel desplaza el centro hacia el borde del mapa:
          - speed 3: paso = (2 hacia borde, 1 lateral) por nivel
          - speed 2: paso = (2 hacia borde, 0 lateral) por nivel
        El resultado se clampea dentro del mapa válido.
        """
        # Dirección del sextante (signos de cx, cy)
        cx_sign = {"arriba_izq": -1, "arriba_medio":  0, "arriba_der":  1,
                   "abajo_izq":  -1, "abajo_medio":   0, "abajo_der":   1}
        cy_sign = {"arriba_izq":  1, "arriba_medio":  1, "arriba_der":  1,
                   "abajo_izq":  -1, "abajo_medio":  -1, "abajo_der":  -1}

        sx = cx_sign[sextant_name]
        sy = cy_sign[sextant_name]

        # Desplazamiento por nivel según speed
        if speed >= 3:
            # En mapas más grandes, la expansión crece un poco con el radio.
            border_step = max(2, self.map_radius // 12)
            lateral_step = 1
        else:
            border_step = max(2, self.map_radius // 12)
            lateral_step = 0

        d = min(self._base_d + self.expansion_level * border_step, self._max_d)
        # Para el desplazamiento lateral: si sx==0 (sextante medio), usar solo y;
        # si sy==0 (imposible en estos sextantes), usar solo x.
        # Lateral = +1 en el eje no-dominante si el sextante tiene dirección en él
        lat_x = lateral_step if sx == 0 else 0
        lat_y = lateral_step if sy == 0 else 0

        x = sx * d + lat_x
        y = sy * d + lat_y

        # Clampear dentro del mapa válido
        lo = -self.map_radius + 2
        hi =  self.map_radius - 2
        x = max(lo, min(hi, x))
        y = max(lo, min(hi, y))

        return Position(x, y)

    # ══════════════════════════════════════════════════════════════════════════
    #  RETORNO A BASE
    # ══════════════════════════════════════════════════════════════════════════

    def _return_to_base_safe(self, position, cargo, hp, radar_contacts, power_distribution):
        # Con cargo SIEMPRE engines:3 — llegar rápido vale más que los escudos.
        # Perder hp en tránsito es aceptable; perder turnos viajando a speed=1 no.
        desired_power = {ENGINES: 3, SHIELDS: 0, LASERS: 0}
        enemies = self._get_enemies_in_radar(radar_contacts)

        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = max(1, desired_power[ENGINES] - cargo)
                # ─────────────────────────────────────────────
        # OPORTUNISMO: agarrar 2do asteroide en camino
        # ─────────────────────────────────────────────
        if cargo == 1:
            asteroids = self._get_nearby_asteroids(radar_contacts)

            # Posición del primer asteroide (último grab)
            first_ast = None
            if self.grabbed_positions:
                # tomar el más reciente (último agregado)
                first_ast = list(self.grabbed_positions)[-1]

            candidates = []
            for ast in asteroids:
                if self._is_position_occupied(ast, radar_contacts):
                    continue

                # puedo llegar este turno
                if not self._is_within_range(position, ast, speed):
                    continue

                # distancia al primer asteroide (mantener coherencia de ruta)
                if first_ast and ast.distance_to(first_ast) > 2:
                    continue

                # Desde ese asteroide, volver a base debe ser rápido
                moves_to_base = self._moves_to_base(ast, max(1, 3 - 2))  
                # explicación abajo ⬇

                if moves_to_base > 3:
                    continue

                candidates.append(ast)
            if candidates:
                target = min(candidates, key=lambda a: position.distance_to(a))
                return FLY_TO, target
                
        # Clasificar tiles de base según visibilidad
        visible_base   = [p for p in self.home_base_positions if p in radar_contacts]
        invisible_base = [p for p in self.home_base_positions if p not in radar_contacts]
        free_visible   = [p for p in visible_base
                          if not self._is_position_occupied(p, radar_contacts)]

        if not visible_base:
            target = min(self.home_base_positions, key=lambda p: position.distance_to(p))
        elif free_visible:
            target = min(free_visible, key=lambda p: position.distance_to(p))
        elif invisible_base:
            target = min(invisible_base, key=lambda p: position.distance_to(p))
        else:
            return None

        if self._is_within_range(position, target, speed):
            return FLY_TO, target

        reachable = self._safe_reachable(position, speed, radar_contacts)
        if not reachable:
            return None

        # if enemies:
        #     closest_enemy = min(enemies, key=lambda e: position.distance_to(e))
        #     if position.distance_to(closest_enemy) <= 5:
        #         safe = [p for p in reachable if p.distance_to(closest_enemy) >= 3]
        #         if safe:
        #             return FLY_TO, min(safe, key=lambda p: p.distance_to(target))

        return FLY_TO, min(reachable, key=lambda p: p.distance_to(target))

    # ══════════════════════════════════════════════════════════════════════════
    #  ESTRATEGIAS SECUNDARIAS
    # ══════════════════════════════════════════════════════════════════════════

    def _low_hp_defense(self, position, cargo, power_distribution, radar_contacts):
        """
        HP < 2 y puntos > 1000: prioridad es sobrevivir.
        - Si tengo cargo: volver a base con engines:2 shields:1 (speed=1 con cargo=1)
        - Si no tengo cargo: farmear con engines:2 shields:1, moviéndome de a 2 tiles
          buscando asteroides igual que siempre, pero sin arriesgar.
        - Una vez que entrego o me matan y respawnean (hp sube), la estrategia
          vuelve a evaluarse turno a turno.
        """
        desired_power = {ENGINES: 2, SHIELDS: 1, LASERS: 0}
        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = 2  # engines:2, sin cargo

        if cargo > 0:
            # Volver a base con speed=max(1, 2-cargo)
            speed_with_cargo = max(1, 2 - cargo)
            visible_base   = [p for p in self.home_base_positions if p in radar_contacts]
            invisible_base = [p for p in self.home_base_positions if p not in radar_contacts]
            free_visible   = [p for p in visible_base
                              if not self._is_position_occupied(p, radar_contacts)]
            if not visible_base:
                target = min(self.home_base_positions, key=lambda p: position.distance_to(p))
            elif free_visible:
                target = min(free_visible, key=lambda p: position.distance_to(p))
            elif invisible_base:
                target = min(invisible_base, key=lambda p: position.distance_to(p))
            else:
                return None
            if self._is_within_range(position, target, speed_with_cargo):
                return FLY_TO, target
            reachable = self._safe_reachable(position, speed_with_cargo, radar_contacts)
            if reachable:
                return FLY_TO, min(reachable, key=lambda p: p.distance_to(target))
            return None

        # Sin cargo: buscar asteroides cercanos moviéndose de a 2
        asteroids_radar = self._get_nearby_asteroids(radar_contacts)
        for ast in sorted(asteroids_radar, key=lambda a: position.distance_to(a)):
            if self._is_within_range(position, ast, speed)                and not self._is_position_occupied(ast, radar_contacts):
                return FLY_TO, ast
        if asteroids_radar:
            closest = min(asteroids_radar, key=lambda a: position.distance_to(a))
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                return FLY_TO, min(free, key=lambda p: p.distance_to(closest))
        # Explorar sextante a speed=2
        center = self._get_expanded_center(self.current_sextant, speed)
        free = self._safe_reachable(position, speed, radar_contacts)
        if free:
            return FLY_TO, min(free, key=lambda p: p.distance_to(center))
        return None

    def _aggressor_mode(self, position, cargo, hp, power_distribution, radar_contacts):
        """
        ≥50% rivales >2000 pts y yo <70% de su promedio.
        Potencia: {engines:1, shields:0, lasers:2}
        - Si tengo cargo: entregar primero (no perder lo que tengo).
        - Sin cargo: buscar enemigos en radar. Si hay uno adyacente (dist=1),
          quedarse en su tile vecino para dañarlo cada turno.
          Si no hay enemigos visibles, moverse por sextantes igual que en farming
          pero buscando SPACESHIP en vez de ASTEROID.
        - enemy_target se actualiza cada turno: si el radar ve a alguien más
          cerca, redirigir.
        """
        desired_power = {ENGINES: 1, SHIELDS: 0, LASERS: 2}
        if power_distribution != desired_power:
            return POWER_TO, desired_power

        speed = 1  # engines:1

        # Con cargo: entregar antes de atacar (no perder puntos)
        if cargo > 0:
            # Volver a base a speed=1 (engines:1 - cargo:1 = 0, mínimo 1)
            visible_base   = [p for p in self.home_base_positions if p in radar_contacts]
            invisible_base = [p for p in self.home_base_positions if p not in radar_contacts]
            free_visible   = [p for p in visible_base
                              if not self._is_position_occupied(p, radar_contacts)]
            if not visible_base:
                target = min(self.home_base_positions, key=lambda p: position.distance_to(p))
            elif free_visible:
                target = min(free_visible, key=lambda p: position.distance_to(p))
            elif invisible_base:
                target = min(invisible_base, key=lambda p: position.distance_to(p))
            else:
                return None
            if self._is_within_range(position, target, speed):
                return FLY_TO, target
            reachable = self._safe_reachable(position, speed, radar_contacts)
            if reachable:
                return FLY_TO, min(reachable, key=lambda p: p.distance_to(target))
            return None

        # Buscar enemigos en radar
        enemies = self._get_enemies_in_radar(radar_contacts)

        # Actualizar enemy_target: si el radar ve alguien más cerca, redirigir
        if enemies:
            closest_enemy = min(enemies, key=lambda e: position.distance_to(e))
            if self.enemy_target is None or                position.distance_to(closest_enemy) < position.distance_to(self.enemy_target):
                self.enemy_target = closest_enemy

        # Limpiar enemy_target si ya no está en radar y pasaron varios turnos
        if self.enemy_target is not None and self.enemy_target not in radar_contacts:
            self.enemy_target = None

        # Si tenemos un objetivo de caza: moverse a un tile adyacente
        if self.enemy_target is not None:
            target = self.enemy_target
            dist = position.distance_to(target)
            if dist <= 1:
                # Ya estamos adyacentes: quedarse (el laser daña automáticamente)
                return None
            # Acercarse a distancia 1
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                # Elegir el tile libre más cercano al enemigo pero que quede a dist>=1
                adjacent_to_enemy = [p for p in free if p.distance_to(target) >= 1]
                if adjacent_to_enemy:
                    return FLY_TO, min(adjacent_to_enemy, key=lambda p: p.distance_to(target))
                return FLY_TO, min(free, key=lambda p: p.distance_to(target))

        # Sin enemigo visible: moverse por sextantes buscando naves
        # (misma lógica que explorar_sextante pero el objetivo es encontrar SPACESHIP)
        self.moves_in_sextant += 1
        if self.moves_in_sextant > self.MAX_MOVES_IN_SEXTANT:
            self._change_sextant(position)
        center = self._get_expanded_center(self.current_sextant, speed)
        free = self._safe_reachable(position, speed, radar_contacts)
        if free:
            return FLY_TO, min(free, key=lambda p: p.distance_to(center))
        return None

    def _mixed_mode_search(self, position, cargo, power_distribution, radar_contacts):
        desired_power = {ENGINES: 2, SHIELDS: 0, LASERS: 1}
        if power_distribution != desired_power:
            return POWER_TO, desired_power
        if cargo >= 2:
            return self._return_to_base_safe(position, cargo, 3, radar_contacts, power_distribution)

        speed = max(1, desired_power[ENGINES] - cargo)
        asteroids_radar = self._get_nearby_asteroids(radar_contacts)

        for ast in sorted(asteroids_radar, key=lambda a: position.distance_to(a)):
            if self._is_within_range(position, ast, speed) \
               and not self._is_position_occupied(ast, radar_contacts):
                return FLY_TO, ast

        if asteroids_radar:
            closest = min(asteroids_radar, key=lambda a: position.distance_to(a))
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                return FLY_TO, min(free, key=lambda p: p.distance_to(closest))

        center = self.sextants.get(self.current_sextant)
        if center:
            free = self._safe_reachable(position, speed, radar_contacts)
            if free:
                return FLY_TO, min(free, key=lambda p: p.distance_to(center))
        return None

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
    
    def _moves_to_base(self, pos, speed):
        dist = self._get_distance_to_base(pos)
        return (dist + speed - 1) // speed  # ceil sin math
    
    def _is_position_occupied(self, target_pos, radar_contacts):
        return any(t == SPACESHIP and p == target_pos for p, t in radar_contacts.items())

    def _is_position_valid(self, pos):
        lo = -self.map_radius + 2
        hi =  self.map_radius - 2
        return lo <= pos.x <= hi and lo <= pos.y <= hi

    def _is_within_range(self, from_pos, to_pos, speed):
        d = from_pos.distance_to(to_pos)
        return 0 < d <= speed

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

    def _moves_to_position(self, from_pos, to_pos, speed):
        dist = from_pos.distance_to(to_pos)
        return (dist + speed - 1) // speed  # ceil

    def _detect_strategy(self, turn_number, cargo, leader_board, hp=3):
        """
        Estrategias en orden de prioridad:
          defend_win   — últimos turnos y voy ganando ampliamente
          low_hp_defense — hp < 2 Y mis puntos > 1000: farmear cauteloso con escudo
          aggressor    — ≥50% rivales tienen >2000 pts Y yo tengo <70% de su promedio
          mixed_mode   — >50% rivales >1000 pts Y yo <1000 pts
          normal       — farming estándar
        """
        turns_remaining = self.total_turns - turn_number
        my_money = leader_board.get(self.player_name, 0)
        others   = [m for p, m in leader_board.items() if p != self.player_name]

        # # 1. Defender victoria inminente
        # if turns_remaining < 4 and others:
        #     if my_money > sum(others) / len(others) + 200:
        #         return "defend_win"

        # # 2. Vida baja con puntos que proteger
        # if hp < 2 and my_money > 1000:
        #     return "low_hp_defense"

        # # 3. Modo atacante: muchos ricos y yo muy por debajo
        # if others:
        #     rich = [m for m in others if m > 2000]
        #     if len(rich) >= len(others) / 2:
        #         avg_rich = sum(rich) / len(rich)
        #         if my_money < avg_rich * 0.70:
        #             return "aggressor"

        # # 4. Modo mixto
        # if others:
        #     num_rich = sum(1 for m in others if m > 1000)
        #     if num_rich > len(others) / 2 and my_money < 1000:
        #         return "mixed_mode"

        return "normal"
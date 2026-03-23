# 🚀 PLANETA_EXPRESS - Guía de Ejecución y Análisis

## Quickstart en WSL

```bash
# 1. Entrar al directorio del proyecto
cd /mnt/host/d/Python_Projects/terminal_velocity

# 2. Ejecutar el bot (simplemente)
bash play_planet.sh

# 3. O con contrincantes personalizados
bash play_planet.sh "Alice:random_aggressor,Bob:random_aggressor"

# 4. O ejecutar + análisis automático
bash run_and_analyze.sh
```

**Nota**: Asegúrate de estar en el directorio correcto antes de ejecutar.

## Ejecución Manual

```bash
# Con formato simple (como el README):
uv run play.py --players Planet_Express:planet_express,Alice:randomaniac,Bob:random_miner --no-ui

# Sin --no-ui para ver el juego en vivo (más lento):
uv run play.py --players Planet_Express:planet_express,Alice:randomaniac,Bob:random_miner

# Con parámetros adicionales:
uv run play.py --players Planet_Express:planet_express,Alice:random_aggressor --turns 150 --map-radius 15 --no-ui
```

## Análisis de Resultados

Después de ejecutar, se genera automáticamente `last_game.log`.

### Análisis Rápido (General)
```bash
python analyze_bot.py
```
Muestra:
- Total de eventos
- Acciones ejecutadas (movimientos, cambios de potencia)
- Minería (asteroides recogidos, entregas)
- Combate (golpes recibidos, muertes)
- Errores y anomalías
- Score final

### Análisis Profundo (Validación de Estrategia)
```bash
python validate_strategy.py
```
Verifica:
- Distribuciones de potencia por modo
- Comportamiento en base (intentos de entrega, tasa de éxito)
- Exploración y eficiencia de movimiento
- Respuesta a peligro (ataques recibidos, ratio de muerte)
- Cumplimiento de estrategia (%)

### Ver Log Crudo
```bash
# Últimas 50 líneas
tail -50 last_game.log

# Buscar eventos específicos del bot
grep -i "planet_express" last_game.log | tail -20

# Contar acciones por tipo
grep -i "planet_express.*action" last_game.log | wc -l
```

## Ejemplo de Output Esperado

```
================================================================================
📊 ANÁLISIS DE PLANET_EXPRESS - TERMINAL VELOCITY
================================================================================

📈 Total de eventos del bot: 287
📝 Total de líneas de log: 1052

🎯 ACCIONES DEL BOT
----------------
✈️  Movimientos (FLY_TO): 85
⚡ Cambios de potencia (POWER_TO): 12
❌ Acciones fallidas: 2

⛏️  MINERÍA DE ASTEROIDES
----------------
🪨 Asteroides recogidos: 42
🏠 Entregas a la base: 21
📊 Ratio de entrega: 50.0%

⚔️  COMBATE
----------------
💥 Golpes recibidos: 8
⚰️  Veces destruido: 2
🎖️  Naves destruidas: 0

================================================================================
✅ VALIDADOR DE ESTRATEGIA - PLANET_EXPRESS
================================================================================

⚡ DISTRIBUCIONES DE POTENCIA
🚀 Modo Minería (3 ENGINES):           10 (83.3%)
🛡️  Modo Defensa (2 ENG, 1 SHIELD):    1 (8.3%)
⚔️  Modo Mixto (2 ENG, 1 LASER):       1 (8.3%)

🏠 COMPORTAMIENTO EN BASE
📍 Intentos de ir a base: 42
✅ Entregas exitosas: 41
📊 Tasa de éxito: 97.6%

✈️  MOVIMIENTO Y EXPLORACIÓN
✈️  Total de movimientos: 85
🪨 Asteroides recogidos: 42
📊 Eficiencia de movimiento: 49.41%

⚠️  RESPUESTA A PELIGRO
💥 Ataques recibidos: 8
⚰️  Muertes: 2
📊 Tasa de muerte tras ataque: 25.0%

📋 RESUMEN DE CUMPLIMIENTO
✅ Cambios de potencia registrados
✅ Movimientos registrados
✅ Asteroides recogidos
✅ Entregas a base
✅ Respuestas a ataques

🎯 Cumplimiento general: 100%
```

## Parámetros Disponibles

```bash
# Ver todos los parámetros disponibles
uv run play.py --help

# Parámetros principales:
--players SPEC              # OBLIGATORIO: especificación de jugadores
--map-radius NUM            # Tamaño del mapa (default: 12)
--turns NUM                 # Número de turnos (default: 100)
--no-ui                     # No mostrar interfaz visual (recomendado para tests)
--ui-turn-delay SECONDS     # Delay entre turnos con UI (default: 0.2)
--repeat NUM                # Repetir N juegos y dar estadísticas
--log-path PATH             # Ruta del archivo de log (default: ./last_game.log)
```

## Repetir Múltiples Juegos (Torneo)

```bash
# Ejecutar 5 partidas y ver estadísticas generales
uv run play.py --players Planet_Express:planet_express,Alice:randomaniac,Bob:random_miner --repeat 5 --no-ui

# O con contrincantes más desafiantes
uv run play.py --players Planet_Express:planet_express,Alice:random_aggressor,Bob:random_aggressor --repeat 10 --no-ui
```

## Troubleshooting

### Error: "zmq not found"
```bash
uv sync  # Instalar dependencias
```

### Error: "BotLogic class not found"
- Verificar que `planet_express.py` esté en la carpeta `bots/`
- Verificar que defina la clase `BotLogic`

### Log vacío o muy corto
- Verificar que el juego no haya fallado
- Ver últimas líneas: `tail -20 last_game.log`

### Cambiar nombre del Bot
En el archivo `bots/planet_express.py`, línea:
```python
self.icon = "🚀"  # Cambiar este icono/nombre
```

## Scripts Disponibles

| Script | Función |
|--------|---------|
| `analyze_bot.py` | Análisis general de comportamiento |
| `validate_strategy.py` | Validación de cumplimiento de estrategia |
| `run_and_analyze.sh` | Script completo: juego + análisis automático |

## Próximos Pasos para Mejorar el Bot

1. **Revisar log** después de cada partida
2. **Identificar patrones** de error o mejora
3. **Ajustar constantes** de estrategia
4. **Testear contra** diferentes oponentes
5. **Medir win rate** con `--repeat 10`

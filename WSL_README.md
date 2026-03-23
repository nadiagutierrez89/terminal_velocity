# 🐧 Ejecutar Planet_Express en WSL

## Paso 1: Acceder al Directorio

```bash
cd /mnt/host/d/Python_Projects/terminal_velocity
```

O en corto:
```bash
cd /mnt/d/Python_Projects/terminal_velocity
```

Verifica que estés en el lugar correcto:
```bash
ls -la      # Deberías ver: play.py, bots/, tv/, etc.
```

## Paso 2: Ejecutar el Bot

**Opción A: Ejecutar Simple (sin análisis)**
```bash
bash play_planet.sh
```

**Opción B: Con Análisis Automático**
```bash
bash run_and_analyze.sh
```

**Opción C: Con Contrincantes Personalizados**
```bash
bash play_planet.sh "Alice:random_aggressor,Bob:random_aggressor"
```

**Opción D: Comando Manual**
```bash
uv run play.py --players Planet_Express:planet_express,Alice:randomaniac,Bob:random_miner --no-ui
```

## Paso 3: Ver Resultados

Después de ejecutar, se genera `last_game.log`:

```bash
# Ver últimas líneas del log
tail -50 last_game.log

# Buscar eventos del bot
grep -i "planet_express" last_game.log | tail -20

# Análisis completo
python3 analyze_bot.py
python3 validate_strategy.py
```

## Troubleshooting

### ❌ "No such file or directory"
- No estás en el directorio correcto
- Solución: `cd /mnt/d/Python_Projects/terminal_velocity`

### ❌ "uv not found"
- UV no está instalado
- Solución: `pip install uv`

### ❌ "play.py not found"
- Estás en la carpeta equivocada
- Verifica: `ls -la play.py` (debe existir)

### ❌ Permission denied en script
```bash
chmod +x play_planet.sh
chmod +x run_and_analyze.sh
bash play_planet.sh
```

## Concepto

- **play_planet.sh**: Script rápido, solo ejecuta el juego
- **run_and_analyze.sh**: Script completo, juego + análisis automático
- **analyze_bot.py**: Analiza logs manualmente después
- **validate_strategy.py**: Valida cumplimiento de estrategia

## Ejemplo Completo

```bash
# Entrar al proyecto
cd /mnt/d/Python_Projects/terminal_velocity

# Ejecutar juego
bash play_planet.sh "Alice:random_miner,Bob:random_aggressor"

# Ver resultados
tail -100 last_game.log

# Análisis detallado
python3 analyze_bot.py last_game.log
python3 validate_strategy.py last_game.log
```

## Repetir Múltiples Veces

```bash
# Jugar 5 partidas (mediante uv)
uv run play.py --players Planet_Express:planet_express,Alice:randomaniac,Bob:random_miner --repeat 5 --no-ui
```

---

**¿Problemas?** Ejecuta:
```bash
cd /mnt/d/Python_Projects/terminal_velocity && ls -la play.py && which uv
```

Esto verificará que estés en el lugar correcto y que `uv` esté disponible.

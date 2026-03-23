#!/bin/bash
# Script simple para ejecutar Planet_Express en WSL

cd "$(dirname "$0")" || exit

echo "🚀 Ejecutando Planet_Express..."
echo ""

# Por defecto Alice:randomaniac,Bob:random_miner si no se especifica
OPPONENTS="${1:-Alice:randomaniac,Bob:random_miner}"

# Ejecutar sin --no-ui para ver la interfaz en tiempo real
uv run play.py --turns 10000 --players Planet_Express:planet_express,$OPPONENTS 

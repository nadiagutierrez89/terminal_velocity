#!/usr/bin/env python3
"""
Analizador de logs de Terminal Velocity para Planet_Express.
Lee el archivo last_game.log y genera un reporte de rendimiento.
"""

import re
from collections import defaultdict
from pathlib import Path


class BotAnalyzer:
    def __init__(self, log_file="last_game.log"):
        self.log_file = Path(log_file)
        self.events = []
        self.planet_express_events = []
        self.parse_log()
    
    def parse_log(self):
        """Parsear el archivo de log"""
        if not self.log_file.exists():
            print(f"❌ Archivo de log no encontrado: {self.log_file}")
            return
        
        with open(self.log_file, 'r') as f:
            for line in f:
                self.events.append(line.strip())
                if "Planet_Express" in line or "planet_express" in line:
                    self.planet_express_events.append(line.strip())
    
    def analyze(self):
        """Analizar el comportamiento del bot"""
        if not self.events:
            print("❌ No se encontraron eventos en el log")
            return
        
        print("\n" + "="*80)
        print("📊 ANÁLISIS DE PLANET_EXPRESS - TERMINAL VELOCITY")
        print("="*80 + "\n")
        
        # Resumen básico
        self._print_summary()
        
        # Acciones del bot
        self._analyze_actions()
        
        # Minería
        self._analyze_mining()
        
        # Combate
        self._analyze_combat()
        
        # Errores
        self._analyze_errors()
        
        # Puntuación final
        self._analyze_final_score()
    
    def _print_summary(self):
        """Resumen general del juego"""
        # Contar eventos de Planet_Express
        total_events = len(self.planet_express_events)
        
        print(f"📈 Total de eventos del bot: {total_events}")
        print(f"📝 Total de líneas de log: {len(self.events)}\n")
    
    def _analyze_actions(self):
        """Analizar acciones realizadas"""
        print("🎯 ACCIONES DEL BOT")
        print("-" * 80)
        
        fly_to_count = 0
        power_to_count = 0
        failed_actions = 0
        
        for event in self.planet_express_events:
            if "action ran ok" in event.lower():
                if "fly_to" in event.lower():
                    fly_to_count += 1
                elif "power" in event.lower():
                    power_to_count += 1
            elif "action failed" in event.lower():
                failed_actions += 1
        
        print(f"✈️  Movimientos (FLY_TO): {fly_to_count}")
        print(f"⚡ Cambios de potencia (POWER_TO): {power_to_count}")
        print(f"❌ Acciones fallidas: {failed_actions}")
        print()
    
    def _analyze_mining(self):
        """Analizar actividad de minería"""
        print("⛏️  MINERÍA DE ASTEROIDES")
        print("-" * 80)
        
        asteroids_grabbed = 0
        home_deliveries = 0
        
        for event in self.planet_express_events:
            if "grabbed an asteroid" in event.lower():
                asteroids_grabbed += 1
            elif "delivered" in event.lower() and "asteroid" in event.lower():
                home_deliveries += 1
        
        print(f"🪨 Asteroides recogidos: {asteroids_grabbed}")
        print(f"🏠 Entregas a la base: {home_deliveries}")
        
        if asteroids_grabbed > 0:
            avg_delivery_ratio = (home_deliveries / asteroids_grabbed) * 100
            print(f"📊 Ratio de entrega: {avg_delivery_ratio:.1f}%")
        print()
    
    def _analyze_combat(self):
        """Analizar estadísticas de combate"""
        print("⚔️  COMBATE")
        print("-" * 80)
        
        hits_taken = 0
        destroyed_count = 0
        ships_destroyed = 0
        
        for event in self.planet_express_events:
            if "hit" in event.lower() and "planet_express" in event.lower():
                hits_taken += 1
            elif "destroyed" in event.lower() and "planet_express" in event.lower():
                destroyed_count += 1
            elif "destroyed by" in event.lower() and "planet_express" in event.lower():
                ships_destroyed += 1
        
        print(f"💥 Golpes recibidos: {hits_taken}")
        print(f"⚰️  Veces destruido: {destroyed_count}")
        print(f"🎖️  Naves destruidas: {ships_destroyed}")
        print()
    
    def _analyze_errors(self):
        """Buscar errores o anomalías"""
        print("⚠️  ERRORES Y ANOMALÍAS")
        print("-" * 80)
        
        errors = []
        warnings = []
        
        for event in self.planet_express_events:
            if "error" in event.lower():
                errors.append(event)
            elif "failed" in event.lower():
                warnings.append(event)
        
        if errors:
            print(f"❌ Errores encontrados: {len(errors)}")
            for error in errors[:5]:  # Mostrar primeros 5
                print(f"   - {error}")
        else:
            print("✅ No se encontraron errores")
        
        if warnings:
            print(f"\n⚠️  Advertencias: {len(warnings)}")
            for warning in warnings[:5]:  # Mostrar primeras 5
                print(f"   - {warning}")
        print()
    
    def _analyze_final_score(self):
        """Analizar puntuación final"""
        print("🏆 RESULTADO FINAL")
        print("-" * 80)
        
        # Buscar línea de ganador
        for event in self.events:
            if "won!" in event.lower():
                print(f"🎉 {event}")
                break
            elif "winners:" in event.lower() or "ending in" in event.lower():
                print(f"📋 {event}")
        
        # Búsqueda final de créditos
        for event in reversed(self.planet_express_events):
            if "credit" in event.lower() or "delivered" in event.lower():
                print(f"💰 {event}")
                break
        print()
    
    def print_raw_events(self, limit=20):
        """Imprimir eventos crudos del bot"""
        print("\n" + "="*80)
        print("📜 ÚLTIMOS EVENTOS DEL BOT (crudos)")
        print("="*80 + "\n")
        
        for event in self.planet_express_events[-limit:]:
            print(event)


def main():
    """Función principal"""
    import sys
    
    log_file = "last_game.log"
    
    # Permitir especificar archivo desde línea de comandos
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    analyzer = BotAnalyzer(log_file)
    analyzer.analyze()
    
    # Mostrar eventos crudos si se pide
    if len(sys.argv) > 2 and sys.argv[2] == "--verbose":
        analyzer.print_raw_events(30)


if __name__ == "__main__":
    main()

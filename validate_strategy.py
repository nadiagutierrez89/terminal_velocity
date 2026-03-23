#!/usr/bin/env python3
"""
Verificador de Estrategia para Planet_Express.
Valida que el bot esté siguiendo su estrategia definida.
"""

import re
from pathlib import Path
from typing import List, Tuple


class StrategyValidator:
    def __init__(self, log_file="last_game.log"):
        self.log_file = Path(log_file)
        self.events = []
        self.bot_name = "Planet_Express"
        self.parse_log()
    
    def parse_log(self):
        """Parsear el archivo de log"""
        if not self.log_file.exists():
            print(f"❌ Archivo de log no encontrado: {self.log_file}")
            return
        
        with open(self.log_file, 'r') as f:
            self.events = [line.strip() for line in f if self.bot_name.lower() in line.lower()]
    
    def validate_strategy(self):
        """Validar que se siga la estrategia"""
        if not self.events:
            print(f"❌ No se encontraron eventos para {self.bot_name}")
            return
        
        print("\n" + "="*80)
        print("✅ VALIDADOR DE ESTRATEGIA - PLANET_EXPRESS")
        print("="*80 + "\n")
        
        # Extraer distribuciones de potencia
        self._validate_power_distributions()
        
        # Validar comportamiento en base
        self._validate_base_behavior()
        
        # Validar comportamiento en exploración
        self._validate_exploration()
        
        # Validar manejo de peligro (naves cercanas)
        self._validate_danger_response()
        
        # Resumen de cumplimiento
        self._print_compliance_summary()
    
    def _validate_power_distributions(self):
        """Validar distribuciones de potencia según modos"""
        print("⚡ DISTRIBUCIONES DE POTENCIA")
        print("-" * 80)
        
        mining_mode = 0  # 3 ENGINES
        defense_mode = 0  # 2 ENGINES 1 SHIELD
        mixed_mode = 0   # 2 ENGINES 1 LASER
        final_mode = 0   # 3 LASERS
        other_modes = 0
        
        power_patterns = {
            "ENGINES: 3": mining_mode,
            "ENGINES: 2, SHIELDS: 1": defense_mode,
            "ENGINES: 2, LASERS: 1": mixed_mode,
            "LASERS: 3": final_mode,
        }
        
        for event in self.events:
            if "power_to applied" in event.lower():
                if "ENGINES: 3" in event:
                    mining_mode += 1
                elif "ENGINES: 2" in event and "SHIELDS: 1" in event:
                    defense_mode += 1
                elif "ENGINES: 2" in event and "LASERS: 1" in event:
                    mixed_mode += 1
                elif "LASERS: 3" in event:
                    final_mode += 1
                else:
                    other_modes += 1
        
        total_distributions = mining_mode + defense_mode + mixed_mode + final_mode + other_modes
        
        if total_distributions > 0:
            print(f"🚀 Modo Minería (3 ENGINES):           {mining_mode} ({mining_mode/total_distributions*100:.1f}%)")
            print(f"🛡️  Modo Defensa (2 ENG, 1 SHIELD):    {defense_mode} ({defense_mode/total_distributions*100:.1f}%)")
            print(f"⚔️  Modo Mixto (2 ENG, 1 LASER):       {mixed_mode} ({mixed_mode/total_distributions*100:.1f}%)")
            print(f"🔫 Modo Defensa Final (3 LASERS):     {final_mode} ({final_mode/total_distributions*100:.1f}%)")
            print(f"❓ Otras distribuciones:               {other_modes}")
        else:
            print("⚠️  No se registraron cambios de potencia")
        print()
    
    def _validate_base_behavior(self):
        """Validar comportamiento en la base"""
        print("🏠 COMPORTAMIENTO EN BASE")
        print("-" * 80)
        
        attempts_to_deliver = 0
        successful_deliveries = 0
        
        for event in self.events:
            if "flew to" in event.lower() and "0, 0" in event:
                attempts_to_deliver += 1
            if "delivered" in event.lower() and "asteroid" in event.lower():
                successful_deliveries += 1
        
        print(f"📍 Intentos de ir a base: {attempts_to_deliver}")
        print(f"✅ Entregas exitosas: {successful_deliveries}")
        
        if attempts_to_deliver > 0:
            success_rate = (successful_deliveries / attempts_to_deliver) * 100
            print(f"📊 Tasa de éxito: {success_rate:.1f}%")
        
        # Verificar si usa escape cuando lleva cargo y hay naves
        escape_behaviors = sum(1 for e in self.events if "flew to" in e.lower() and "flew to" in e.lower())
        print(f"🏃 Comportamientos de escape: {escape_behaviors}")
        print()
    
    def _validate_exploration(self):
        """Validar exploración del territorio"""
        print("🗺️  EXPLORACIÓN Y MOVIMIENTO")
        print("-" * 80)
        
        total_movements = 0
        asteroid_grabs = 0
        movements_to_known = 0
        movements_to_unknown = 0
        
        for event in self.events:
            if "flew to" in event.lower():
                total_movements += 1
            if "grabbed an asteroid" in event.lower():
                asteroid_grabs += 1
        
        print(f"✈️  Total de movimientos: {total_movements}")
        print(f"🪨 Asteroides recogidos: {asteroid_grabs}")
        
        if total_movements > 0:
            grab_rate = (asteroid_grabs / total_movements) * 100
            print(f"📊 Eficiencia de movimiento: {grab_rate:.2f}% (asteroides/movimientos)")
        print()
    
    def _validate_danger_response(self):
        """Validar respuesta ante peligro"""
        print("⚠️  RESPUESTA A PELIGRO")
        print("-" * 80)
        
        attacked_events = sum(1 for e in self.events if "hit" in e.lower() and "damage" in e.lower())
        destroyed_events = sum(1 for e in self.events if "destroyed" in e.lower())
        escape_events = sum(1 for e in self.events if "away" in e.lower())
        
        print(f"💥 Ataques recibidos: {attacked_events}")
        print(f"⚰️  Muertes: {destroyed_events}")
        print(f"🏃 Acciones de escape detectadas: {escape_events}")
        
        # Ratio de muertes a vida
        if attacked_events > 0:
            death_rate = (destroyed_events / attacked_events) * 100
            print(f"📊 Tasa de muerte tras ataque: {death_rate:.1f}%")
        print()
    
    def _print_compliance_summary(self):
        """Resumen de cumplimiento de estrategia"""
        print("📋 RESUMEN DE CUMPLIMIENTO")
        print("-" * 80)
        
        checklist = {
            "Cambios de potencia registrados": any("power_to" in e for e in self.events),
            "Movimientos registrados": any("flew to" in e for e in self.events),
            "Asteroides recogidos": any("grabbed" in e for e in self.events),
            "Entregas a base": any("delivered" in e for e in self.events),
            "Respuestas a ataques": any("hit" in e for e in self.events),
        }
        
        for check, passed in checklist.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}")
        
        total_checks = len(checklist)
        passed_checks = sum(1 for v in checklist.values() if v)
        compliance = (passed_checks / total_checks) * 100
        
        print(f"\n🎯 Cumplimiento general: {compliance:.0f}%")
        print()


def main():
    """Función principal"""
    import sys
    
    log_file = "last_game.log"
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    validator = StrategyValidator(log_file)
    validator.validate_strategy()


if __name__ == "__main__":
    main()

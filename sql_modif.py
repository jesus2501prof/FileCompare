import re
import os
from pathlib import Path

# Configuración de colores para la terminal
class bcolors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def procesar_sql(contenido):
    cambios_realizados = False
    
    # Guardar contenido original para comparación
    original = contenido
    
    # 1. Reemplazar JOIN por INNER JOIN (sin afectar LEFT/RIGHT/OUTER/etc. JOIN)
    join_pattern = re.compile(r'(?<!\w)(?<!\bINNER\s)(?<!\bLEFT\s)(?<!\bRIGHT\s)(?<!\bFULL\s)(?<!\bOUTER\s)\bJOIN\b', re.IGNORECASE)
    contenido = join_pattern.sub('INNER JOIN', contenido)
    
    # Verificar si hubo cambios en los JOIN
    if contenido != original:
        cambios_realizados = True
        original = contenido
    
    # 2. Agregar WITH (NOLOCK) a tablas en SELECT (excepto en UPDATE/DELETE)
    if 'UPDATE ' not in contenido.upper() and 'DELETE ' not in contenido.upper():
        # Patrón mejorado para identificar nombres de tabla en FROM/JOIN
        table_pattern = re.compile(r'''
            (\bFROM\b|\b(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s+JOIN\b)\s+   # Cláusula FROM o JOIN
            (?:                           # Nombre de tabla puede ser:
            (\[[^\]]+\]\.\[[^\]]+\])     # [esquema].[tabla]
            |(\[[^\]]+\])                 # [tabla]
            |([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)  # esquema.tabla
            |([a-zA-Z_#@][\w]*)          # tabla simple (incluye # y @)
            |(\(.*?\))                   # subconsultas entre paréntesis
            )
            (?:\s+(?:AS\s+)?            # Alias opcional
            (?:(\[[^\]]+\])|([a-zA-Z_][\w]*))?  # Alias con corchetes o sin ellos
            )?
        ''', re.IGNORECASE | re.VERBOSE | re.DOTALL)
        
        def agregar_nolock(match):
            nonlocal cambios_realizados
            full_match = match.group(0)
            if 'WITH (NOLOCK)' in full_match.upper():
                return full_match
            
            parts = list(match.groups())
            clause = parts[0]
            
            table_name = ''
            if parts[1]: table_name = parts[1]
            elif parts[2]: table_name = parts[2]
            elif parts[3] and parts[4]: table_name = f"{parts[3]}.{parts[4]}"
            elif parts[5]: table_name = parts[5]
            elif parts[6]: return full_match
            
            if table_name.startswith('#') or table_name.startswith('@'):
                return full_match
            
            alias = ''
            if parts[7]: alias = parts[7]
            elif parts[8]: alias = parts[8]
            
            cambios_realizados = True
            result = f"{clause} {table_name}"
            if alias:
                result += f" {alias}"
            result += " WITH (NOLOCK)"
            
            return result
        
        contenido = table_pattern.sub(agregar_nolock, contenido)
    
    return contenido, cambios_realizados

def procesar_archivo(archivo):
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        contenido_modificado, cambios = procesar_sql(contenido)
        
        if cambios:
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write(contenido_modificado)
            print(f"{bcolors.GREEN}[MODIFICADO]{bcolors.ENDC} {archivo}")
        else:
            print(f"{bcolors.BLUE}[SIN CAMBIOS]{bcolors.ENDC} {archivo}")
    
    except Exception as e:
        print(f"{bcolors.RED}[ERROR]{bcolors.ENDC} {archivo} - {str(e)}")

def procesar_directorio(directorio):
    total_archivos = 0
    modificados = 0
    errores = 0
    
    for root, _, files in os.walk(directorio):
        for file in files:
            if file.lower().endswith('.sql'):
                total_archivos += 1
                archivo_completo = os.path.join(root, file)
                procesar_archivo(archivo_completo)
    
    # Resumen estadístico
    print(f"\n{bcolors.BOLD}Resumen del procesamiento:{bcolors.ENDC}")
    print(f"- Archivos procesados: {total_archivos}")
    print(f"- {bcolors.GREEN}Archivos modificados: {modificados}{bcolors.ENDC}")
    print(f"- {bcolors.BLUE}Archivos sin cambios: {total_archivos - modificados - errores}{bcolors.ENDC}")
    print(f"- {bcolors.RED}Archivos con errores: {errores}{bcolors.ENDC}")

def main():
    if len(sys.argv) != 2:
        print(f"Uso: python {sys.argv[0]} <directorio>")
        sys.exit(1)
    
    directorio = sys.argv[1]
    
    if not os.path.isdir(directorio):
        print(f"{bcolors.RED}Error: {directorio} no es un directorio válido{bcolors.ENDC}")
        sys.exit(1)
    
    print(f"\n{bcolors.BOLD}Iniciando procesamiento recursivo en: {directorio}{bcolors.ENDC}\n")
    procesar_directorio(directorio)
    print(f"\n{bcolors.BOLD}Procesamiento completado{bcolors.ENDC}")

if __name__ == "__main__":
    import sys
    main()
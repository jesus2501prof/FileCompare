import re
import os
from pathlib import Path

class bcolors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def procesar_sql(contenido):
    cambios_realizados = False
    original = contenido
    
    # 1. Reemplazar JOIN por INNER JOIN (versión insensible a mayúsculas/minúsculas)
    def replacer(match):
        nonlocal cambios_realizados
        cambios_realizados = True
        return match.group(1) + 'INNER JOIN'
    
    # Patrón que evita modificar JOINs que ya tienen calificador
    join_pattern = re.compile(r'''
        (^|\s)                    # Inicio de línea o espacio
        (?!                       # Negative lookahead para JOINs que no queremos modificar
          (?:INNER|LEFT|RIGHT|FULL|OUTER|LOOP|HASH|MERGE)\s+JOIN  # JOINs con calificador
          |JOIN\s+[^ ]+\s*WITH    # JOINs que ya tienen WITH
        )\b(join)\b               # Solo capturamos 'join' en minúsculas (por el flag IGNORECASE)
        (?=\s)                    # Seguido de espacio
    ''', re.IGNORECASE | re.VERBOSE | re.MULTILINE)
    
    contenido = join_pattern.sub(replacer, contenido)
    
    # 2. Agregar WITH (NOLOCK) a todas las tablas, incluyendo subconsultas
    # Excepto en operaciones UPDATE/DELETE directas
    is_update_or_delete = re.search(r'^\s*(?:UPDATE|DELETE)\b', contenido, re.IGNORECASE | re.MULTILINE)
    
    if not is_update_or_delete:
        # Patrón mejorado que detecta tablas en FROM/JOIN incluyendo subconsultas
        table_pattern = re.compile(r'''
            (\bfrom\b|\b(?:inner|left|right|full|outer)?\s+(?:loop|hash|merge)?\s*join\b)\s+  # Cláusula FROM o JOIN
            (
                (?:\[[^\]]+\]\.\[[^\]]+\]|\[[^\]]+\]|[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*|[a-zA-Z_#@][\w]*)  # Nombre de tabla
                (?!\s*\b(?:with|where|group|having|order|union|except|intersect)\b)  # No capturar palabras clave después
            )
            (?:\s+(?:as\s+)?(\[[^\]]+\]|[a-zA-Z_][\w]*)?)?  # Alias opcional
            (?=\s+|$)  # Lookahead para espacio o fin de línea
        ''', re.IGNORECASE | re.VERBOSE)
        
        def agregar_nolock(match):
            nonlocal cambios_realizados
            full_match = match.group(0)
            if 'with (nolock)' in full_match.lower():
                return full_match
            
            clause = match.group(1)  # FROM o JOIN
            table_name = match.group(2)  # Nombre de tabla
            alias = match.group(3)  # Alias si existe
            
            # Omitir solo tablas temporales y variables de tabla
            if table_name.startswith('#') or table_name.startswith('@'):
                return full_match
            
            # Determinar si lo que sigue es una palabra clave SQL
            next_text = contenido[match.end():match.end()+20]
            if any(re.match(r'^\s*\b'+kw+r'\b', next_text, re.IGNORECASE) 
               for kw in ['where', 'group', 'having', 'order', 'union', 'except', 'intersect', 'on']):
                alias = None
            
            cambios_realizados = True
            if alias:
                return f"{clause} {table_name} {alias} WITH (NOLOCK)"
            else:
                return f"{clause} {table_name} WITH (NOLOCK)"
        
        # Procesar todo el contenido (incluyendo subconsultas)
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
    for root, _, files in os.walk(directorio):
        for file in files:
            if file.lower().endswith('.sql'):
                archivo_completo = os.path.join(root, file)
                procesar_archivo(archivo_completo)

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
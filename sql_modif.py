import re
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Inicializar colorama para colores en terminal
init()

def print_colored(status, message):
    """Imprime mensajes con color según el estado"""
    colors = {
        'modified': Fore.GREEN,
        'unchanged': Fore.BLUE,
        'error': Fore.RED,
        'info': Fore.CYAN
    }
    print(f"{colors[status]}{message}{Style.RESET_ALL}")

def normalize_case(sql_content):
    """Normaliza palabras clave SQL a mayúsculas"""
    keywords = ['SELECT', 'FROM', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'FULL', 'OUTER', 
                'WHERE', 'HAVING', 'EXISTS', 'WITH', 'NOLOCK', 'UPDATE', 'DELETE', 'AS']
    
    for keyword in keywords:
        sql_content = re.sub(r'\b' + keyword + r'\b', keyword, sql_content, flags=re.IGNORECASE)
    return sql_content

def normalize_joins(sql_content):
    """Reemplaza JOIN puros por INNER JOIN"""
    pattern = re.compile(r'(?<!\w)(JOIN)(?!\s*\w+ JOIN)', re.IGNORECASE)
    return pattern.sub('INNER JOIN', sql_content)

def add_nolock_to_subqueries(sql_content):
    """Agrega WITH (NOLOCK) a subconsultas en WHERE/HAVING"""
    subquery_pattern = re.compile(
        r'(WHERE|HAVING)\s*(NOT\s*)?(EXISTS\s*)?\(?\s*(SELECT\s+.+?\s+FROM\s+.+?)(?=\s*(?:WITH\s*\(|\)|\s+WHERE|\s+GROUP|\s+HAVING|\s+ORDER|\s+FOR|$))',
        re.IGNORECASE | re.DOTALL
    )
    
    def process_subquery(match):
        prefix = match.group(1).upper()
        not_exists = match.group(2) or ''
        exists_keyword = match.group(3) or ''
        subquery = match.group(4)
        processed_subquery = add_nolock_hints(subquery, is_main_query=False)
        return f"{prefix}{not_exists}{exists_keyword}({processed_subquery}"

    return subquery_pattern.sub(process_subquery, sql_content)

def add_nolock_hints(sql_content, is_main_query=True):
    """Agrega WITH (NOLOCK) a tablas calificadas"""
    table_ref_pattern = re.compile(
        r'(FROM|JOIN)\s+(?![\#@])((\[?\w+\]?\.)?\[?\w+\]?)(\s+(AS\s+)?\w*\s*)?(?!(WITH\s*\(\s*NOLOCK\s*\)))',
        re.IGNORECASE
    )
    
    def add_hint(match):
        if is_main_query and re.search(r'^\s*(UPDATE|DELETE)\b', sql_content[:match.start()], re.IGNORECASE):
            return match.group(0)
        return f"{match.group(1)} {match.group(2)}{match.group(4) or ''} WITH (NOLOCK)"
    
    return table_ref_pattern.sub(add_hint, sql_content)

def process_sql_file(file_path):
    """Procesa un archivo SQL y devuelve si fue modificado"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            original_content = file.read()
        
        # Paso 1: Normalizar JOINs
        step1 = normalize_joins(original_content)
        
        # Paso 2: Procesar subconsultas
        step2 = add_nolock_to_subqueries(step1)
        
        # Paso 3: Procesar consulta principal
        step3 = add_nolock_hints(step2)
        
        # Paso 4: Normalizar mayúsculas
        final_content = normalize_case(step3)
        
        if final_content == original_content:
            return 'unchanged'
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(final_content)
        return 'modified'
        
    except Exception as e:
        print_colored('error', f"Error procesando {file_path}: {str(e)}")
        return 'error'

def process_directory(root_dir):
    """Procesa recursivamente todos los archivos .sql en un directorio"""
    root_path = Path(root_dir)
    if not root_path.exists():
        print_colored('error', f"El directorio {root_dir} no existe")
        return
    
    print_colored('info', f"\nAnalizando directorio: {root_path.resolve()}")
    
    modified_count = 0
    unchanged_count = 0
    error_count = 0
    
    for sql_file in root_path.rglob('*.sql'):
        result = process_sql_file(sql_file)
        
        if result == 'modified':
            print_colored('modified', f"MODIFICADO: {sql_file}")
            modified_count += 1
        elif result == 'unchanged':
            print_colored('unchanged', f"SIN CAMBIOS: {sql_file}")
            unchanged_count += 1
        else:
            error_count += 1
    
    print_colored('info', f"\nResumen:")
    print_colored('modified', f"Archivos modificados: {modified_count}")
    print_colored('unchanged', f"Archivos sin cambios: {unchanged_count}")
    print_colored('error', f"Archivos con errores: {error_count}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python sql_normalizer.py <directorio>")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    process_directory(target_dir)
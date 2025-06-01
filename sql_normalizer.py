import re
from pathlib import Path
from datetime import datetime

class SQLNormalizer:
    def __init__(self, normalize_joins=True, add_nolock=True):
        self.normalize_joins = normalize_joins
        self.add_nolock = add_nolock
        
    def normalize_sql_joins(self, content):
        """Normaliza JOINs no calificados añadiendo INNER"""
        if not self.normalize_joins:
            return content
            
        join_types = {'inner', 'left', 'right', 'full', 'cross', 'loop', 'merge', 'hash'}
        pattern = re.compile(
            r'(\b(?:' + '|'.join(join_types) + r')\s+join\b)|(\bjoin\b)', 
            flags=re.IGNORECASE
        )
        
        def replacer(m):
            return m.group(1) if m.group(1) else f'INNER {m.group(2)}'
        
        return pattern.sub(replacer, content)
    
    def add_nolock_hints(self, content):
        """Agrega WITH (NOLOCK) a tablas en FROM/JOIN de manera precisa"""
        if not self.add_nolock:
            return content
            
        # Patrón mejorado para detectar tablas con su contexto completo
        table_pattern = re.compile(
            r'(?P<prefix>\b(?:FROM|JOIN)\s+)'  # Palabra clave
            r'(?P<table>(?!(?:\#|@|tempdb\.))'  # Excluir tablas temporales
            r'(?:(?:\w+\.){0,2}\w+))'  # Nombre de tabla
            r'(?P<alias>\s+(?:AS\s+)?\w+)?'  # Alias opcional
            r'(?P<existing_hint>\s+WITH\s*\(\s*NOLOCK\s*\))?',  # Hint existente
            flags=re.IGNORECASE
        )
        
        # Operaciones que no deben tener NOLOCK
        no_nolock_ops = re.compile(
            r'\b(?:UPDATE|DELETE|INSERT|MERGE|TRUNCATE)\b',
            flags=re.IGNORECASE
        )
        
        def add_hint(match):
            if no_nolock_ops.search(match.string[:match.start()]):
                return match.group(0)
                
            # Si ya tiene el hint, no modificar
            if match.group('existing_hint'):
                return match.group(0)
                
            # Construir el reemplazo
            replacement = match.group('prefix') + match.group('table')
            if match.group('alias'):
                replacement += match.group('alias')
            replacement += ' WITH (NOLOCK)'
            
            return replacement
        
        return table_pattern.sub(add_hint, content)
    
    def normalize_content(self, content):
        """Aplica todas las normalizaciones activas conservando formato"""
        # Conservar saltos de línea y formato original
        lines = content.splitlines()
        normalized_lines = []
        
        for line in lines:
            normalized_line = line
            if self.normalize_joins:
                normalized_line = self.normalize_sql_joins(normalized_line)
            if self.add_nolock:
                normalized_line = self.add_nolock_hints(normalized_line)
            normalized_lines.append(normalized_line)
        
        return '\n'.join(normalized_lines)
    
    def process_file(self, file_path, create_backup=True):
        """Procesa un archivo SQL con manejo robusto de formato"""
        try:
            path = Path(file_path)
            original = path.read_text(encoding='utf-8')
            normalized = self.normalize_content(original)
            
            if normalized != original:
                if create_backup:
                    backup_path = f"{file_path}.bak"
                    Path(backup_path).write_text(original, encoding='utf-8')
                
                path.write_text(normalized, encoding='utf-8')
                changes = []
                if self.normalize_joins:
                    changes.append("JOINs normalizados")
                if self.add_nolock:
                    changes.append("WITH (NOLOCK) agregado")
                return f"✓ {path.name} modificado ({', '.join(changes)})"
            return f"→ {path.name} no requería cambios"
        
        except Exception as e:
            return f"✗ Error procesando {path.name}: {str(e)}"

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Normalizador de SQL mejorado')
    parser.add_argument('files', nargs='+', help='Archivos SQL a procesar')
    parser.add_argument('--no-joins', action='store_false', dest='normalize_joins',
                       help='Desactivar normalización de JOINs')
    parser.add_argument('--no-nolock', action='store_false', dest='add_nolock',
                       help='Desactivar agregado de WITH (NOLOCK)')
    parser.add_argument('--no-backup', action='store_false', dest='create_backup',
                       help='No crear archivos de backup')
    
    args = parser.parse_args()
    
    normalizer = SQLNormalizer(
        normalize_joins=args.normalize_joins,
        add_nolock=args.add_nolock
    )
    
    for file_path in args.files:
        path = Path(file_path)
        if path.is_file() and path.suffix.lower() == '.sql':
            result = normalizer.process_file(path, args.create_backup)
            print(result)
        else:
            print(f"✗ {file_path} no es un archivo .sql válido")

if __name__ == "__main__":
    main()
import os
from difflib import Differ, SequenceMatcher
from PIL import Image, ImageDraw, ImageFont

def compare_directories(dir1, dir2, output_dir, context_lines=2, max_gap=5, 
                       split_images=0, max_height=1000, highlight_partial=0,
                       file_extensions=None):
    """
    Compara directorios mostrando SOLO diferencias reales:
    - Omite líneas vacías en la comparación
    - No genera imágenes para archivos sin cambios
    - Archivos nuevos siguen mostrándose completos
    """
    # Validación y configuración inicial (igual que antes)
    for dir_path in [dir1, dir2]:
        if not os.path.isdir(dir_path):
            raise ValueError(f"El directorio no existe: {dir_path}")

    dir1 = os.path.normpath(dir1)
    dir2 = os.path.normpath(dir2)
    output_dir = os.path.normpath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if file_extensions:
        file_extensions = [ext.lower() if ext.startswith('.') else f".{ext.lower()}" 
                         for ext in file_extensions]
        print(f"\nProcesando solo archivos con extensiones: {', '.join(file_extensions)}")

    def get_valid_files(directory):
        return {f for f in os.listdir(directory) 
                if os.path.isfile(os.path.join(directory, f)) and
                (not file_extensions or 
                 os.path.splitext(f)[1].lower() in file_extensions)}
    
    files_dir1 = get_valid_files(dir1)
    files_dir2 = get_valid_files(dir2)

    # Procesar archivos comunes
    for filename in sorted(files_dir1 & files_dir2):
        try:
            file1_path = os.path.join(dir1, filename)
            file2_path = os.path.join(dir2, filename)
            
            print(f"\nAnalizando: {filename}")
            
            # Leer archivos omitiendo líneas vacías
            with open(file1_path, 'r', encoding='utf-8', errors='ignore') as f1:
                file1_lines = [line.rstrip('\n') for line in f1 if line.strip()]
            
            with open(file2_path, 'r', encoding='utf-8', errors='ignore') as f2:
                file2_lines = [line.rstrip('\n') for line in f2 if line.strip()]
            
            # Procesar diferencias
            differ = Differ()
            diff = [line for line in differ.compare(file1_lines, file2_lines) 
                   if not line.startswith('  ') or line[2:].strip()]
            
            if not diff:
                print(f"  Sin diferencias detectadas - omitiendo")
                continue
                
            lines_to_show = process_diff(diff, file1_lines, file2_lines, context_lines, max_gap)
            
            if not lines_to_show:
                print(f"  Sin cambios importantes - omitiendo")
                continue
                
            # Generar imágenes solo si hay diferencias
            generate_comparison_images(
                lines_to_show=lines_to_show,
                output_path=os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.png"),
                split_images=split_images,
                max_height=max_height,
                highlight_partial=highlight_partial,
                is_new_file=False
            )
            
        except Exception as e:
            print(f"Error procesando {filename}: {str(e)}")

    # Procesar archivos nuevos (mostrar completos)
    for filename in sorted(files_dir2 - files_dir1):
        try:
            file2_path = os.path.join(dir2, filename)
            print(f"\nProcesando NUEVO archivo: {filename}")
            
            with open(file2_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.rstrip('\n') for line in f if line.strip()] or ["[ARCHIVO VACÍO]"]
            
            generate_comparison_images(
                lines_to_show=[('new', i, line, None) for i, line in enumerate(lines)],
                output_path=os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_NUEVO.png"),
                split_images=split_images,
                max_height=max_height,
                highlight_partial=False,
                is_new_file=True
            )
            
        except Exception as e:
            print(f"Error procesando nuevo archivo {filename}: {str(e)}")

def process_diff(diff, file1_lines, file2_lines, context_lines, max_gap):
    """Procesa diferencias ignorando líneas vacías"""
    changes = []
    file1_pos = 0
    file2_pos = 0
    
    for line in diff:
        if line.startswith('  '):
            file1_pos += 1
            file2_pos += 1
        elif line.startswith('- '):
            changes.append(('del', file1_pos, line[2:], 
                          file2_lines[file2_pos] if file2_pos < len(file2_lines) else ""))
            file1_pos += 1
        elif line.startswith('+ '):
            changes.append(('add', file2_pos, line[2:],
                          file1_lines[file1_pos - 1] if file1_pos > 0 and (file1_pos - 1) < len(file1_lines) else ""))
            file2_pos += 1

    # Agrupar cambios cercanos
    grouped_changes = []
    current_group = []
    last_pos = -max_gap - 1
    
    for change in changes:
        if change[1] - last_pos > max_gap:
            if current_group:
                grouped_changes.append(current_group)
            current_group = []
        current_group.append(change)
        last_pos = change[1]
    
    if current_group:
        grouped_changes.append(current_group)
    
    # Construir resultado con contexto
    lines_to_show = []
    for group in grouped_changes:
        first_line = group[0][1]
        last_line = group[-1][1]
        
        # Contexto antes
        start = max(0, first_line - context_lines)
        for i in range(start, first_line):
            lines_to_show.append(('ctx', i, file1_lines[i], None))
        
        # Cambios
        for change in group:
            lines_to_show.append(change)
        
        # Contexto después
        end = min(last_line + context_lines + 1, max(len(file1_lines), len(file2_lines)))
        for i in range(last_line + 1, end):
            line_content = file1_lines[i] if i < len(file1_lines) else ''
            if i < len(file2_lines) and line_content != file2_lines[i]:
                line_content = file2_lines[i]
            lines_to_show.append(('ctx', i, line_content, None))
        
        # Separador
        if lines_to_show:  # Solo añadir si hay contenido
            lines_to_show.append(('sep', None, None, None))
    
    return lines_to_show

def generate_comparison_images(lines_to_show, output_path, split_images, 
                             max_height, highlight_partial, is_new_file):
    """Genera imágenes solo si hay contenido válido"""
    if not lines_to_show:
        return

    # Configuración visual
    try:
        font = ImageFont.truetype("consola.ttf", 14) if os.name == 'nt' else ImageFont.truetype("DejaVuSansMono.ttf", 14)
    except:
        font = ImageFont.load_default()
    
    line_height = 20
    char_width = 8
    margin = 10
    gutter_width = 60
    
    # Calcular dimensiones
    max_line_length = max((len(line[2]) for line in lines_to_show if line[2]), default=50)
    img_width = (max_line_length * char_width) + (margin * 4) + (gutter_width * 2)

    # Función para crear imagen individual
    def create_image(start_idx, end_idx, img_num):
        img_height = ((end_idx - start_idx) * line_height) + (margin * 2)
        img = Image.new('RGB', (img_width, img_height), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        
        y_pos = margin
        for i in range(start_idx, end_idx):
            line_type, line_num, content, _ = lines_to_show[i]
            
            if line_type == 'sep':
                draw.line([(margin, y_pos + line_height//2), 
                          (img_width - margin, y_pos + line_height//2)], 
                         fill=(80, 80, 80), width=1)
                y_pos += line_height
                continue
            
            # Estilos
            if is_new_file:
                bg_color = (20, 50, 20)  # Fondo verde oscuro
                text_color = (150, 255, 150)  # Texto verde claro
                prefix = '+ '
                num_color = (100, 255, 100)
            else:
                bg_color, text_color, prefix, num_color = {
                    'del': ((70, 30, 30), (255, 180, 180), '- ', (255, 150, 150)),
                    'add': ((30, 70, 30), (180, 255, 180), '+ ', (150, 255, 150)),
                    'ctx': ((45, 45, 45), (200, 200, 200), '  ', (150, 150, 150))
                }.get(line_type, ((45, 45, 45), (200, 200, 200), '  ', (150, 150, 150)))
            
            # Dibujar línea
            draw.rectangle([(margin, y_pos), (img_width - margin, y_pos + line_height)], 
                          fill=bg_color)
            
            # Número de línea (si aplica)
            if line_num is not None:
                draw.text((margin + 5, y_pos + 3), f"{line_num + 1:>4}", 
                         fill=num_color, font=font)
            
            # Contenido
            text_x = margin + gutter_width
            draw.text((text_x, y_pos + 3), prefix, fill=text_color, font=font)
            draw.text((text_x + font.getlength(prefix), y_pos + 3), 
                     content, fill=text_color, font=font)
            
            y_pos += line_height
        
        # Guardar imagen
        final_path = output_path if img_num == 1 else output_path.replace(".png", f"_{img_num-1}.png")
        img.save(final_path)
        print(f"  Imagen generada: {os.path.basename(final_path)}")

    # Generar una o múltiples imágenes
    if not split_images or len(lines_to_show) * line_height <= max_height:
        create_image(0, len(lines_to_show), 1)
    else:
        current_start = 0
        img_num = 1
        max_lines_per_img = (max_height - 2 * margin) // line_height
        
        for i in range(len(lines_to_show)):
            if i > current_start and (i - current_start) >= max_lines_per_img:
                # Buscar punto de división óptimo
                split_at = i
                for j in range(i, min(i + 10, len(lines_to_show))):
                    if lines_to_show[j][0] == 'sep':
                        split_at = j + 1
                        break
                
                if split_at > current_start:
                    create_image(current_start, split_at, img_num)
                    current_start = split_at
                    img_num += 1
        
        if current_start < len(lines_to_show):
            create_image(current_start, len(lines_to_show), img_num)

# Ejemplo de uso
if __name__ == "__main__":
    compare_directories(
        dir1="A:\Descargas\jesus2501profesional\StressForkMaster\SqlQueryStress\src\SQLQueryStress",
        dir2="A:\Descargas\jesus2501profesional\SqlQueryStress\src\SQLQueryStress",
        output_dir="evidencia_construccion",
        context_lines=2,
        max_gap=5,
        split_images=1,
        max_height=1000,
        highlight_partial=0,
        file_extensions=['.py', '.txt', '.cs']  # Opcional: filtrar por extensiones
    )
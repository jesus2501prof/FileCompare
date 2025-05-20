param (
    [Parameter(Mandatory=$true, HelpMessage="Ingresa la ruta de la carpeta a copiar")]
    [string]$rutaOrigen
)

# Configuración
$rutaCopia = $rutaOrigen + "_copia"

# 1. Validar carpeta origen
if (-not (Test-Path -Path $rutaOrigen)) {
    Write-Host "Error: La carpeta de origen '$rutaOrigen' no existe."
    exit
}

# 2. Copiar todo
try {
    Copy-Item -Path $rutaOrigen -Destination $rutaCopia -Recurse -Force -ErrorAction Stop
    Write-Host "Copia completada en '$rutaCopia'."
} catch {
    Write-Host "¡Error al copiar! No se borrará la carpeta original."
    exit
}

# 3. Actualizar fechas (creación y modificación) de TODOS los archivos copiados
Write-Host "Actualizando fechas a la hora actual..."
Get-ChildItem -Path $rutaCopia -Recurse -File | ForEach-Object {
    $fechaActual = Get-Date
    $_.CreationTime = $fechaActual
    $_.LastWriteTime = $fechaActual
    $_.LastAccessTime = $fechaActual
}

# 4. Validar integridad (opcional, pero recomendado)
$archivosOrigen = (Get-ChildItem -Path $rutaOrigen -Recurse -File).Count
$archivosCopia = (Get-ChildItem -Path $rutaCopia -Recurse -File).Count
if ($archivosOrigen -ne $archivosCopia) {
    Write-Host "¡Error! La copia tiene $archivosCopia archivos (original: $archivosOrigen)."
    Remove-Item -Path $rutaCopia -Recurse -Force
    exit
}

# 5. Borrar original
try {
    Remove-Item -Path $rutaOrigen -Recurse -Force -ErrorAction Stop
    Write-Host "Carpeta original eliminada."
} catch {
    Write-Host "¡Error al borrar la original! La copia se mantiene en '$rutaCopia'."
    exit
}

# 6. Renombrar copia
if (-not (Test-Path -Path $rutaOrigen)) {
    Rename-Item -Path $rutaCopia -NewName $rutaOrigen -ErrorAction Stop
    Write-Host "¡Proceso completado! Carpeta renombrada a '$rutaOrigen'."
} else {
    Write-Host "¡Error! No se pudo renombrar (ya existe '$rutaOrigen'). La copia está en '$rutaCopia'."
}

# .\copia_y_renombra.ps1 -rutaOrigen "C:\Tu\Carpeta\Origen"
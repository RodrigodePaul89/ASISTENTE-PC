# Mimi Brave Context Bridge

Extension local para Brave que envia a Mimi el titulo y URL de la pestana activa.

## Instalacion en Brave

1. Abre `brave://extensions`.
2. Activa `Developer mode`.
3. Pulsa `Load unpacked`.
4. Selecciona esta carpeta: `ASISTENTE-PC/browser_extensions/mimi_brave_context`.

## Requisito en Mimi

Mimi debe estar ejecutandose con el servidor local de contexto activo en `127.0.0.1:37655`.

Comando en Mimi para verificar:
- `estado contexto navegador`

## Alcance

- Envia solo metadatos: titulo y URL de pestana activa.
- No descarga archivos ni ejecuta acciones del sistema desde el navegador.

# Asistente IA local y privado (Windows)

Esta guia esta pensada para tu hardware actual:
- CPU: Ryzen 5 7520U
- RAM: 7.28 GB
- GPU integrada AMD (0.5 GB VRAM)

Objetivo: usar IA local para que tus datos no salgan de tu PC.

## 1) Modelos recomendados

Prioridad para este equipo: modelos pequenos cuantizados.

- Recomendado: `qwen2.5:1.5b-instruct`
- Alternativa: `gemma2:2b`
- Muy ligero: `tinyllama`

Evita por ahora modelos de 7B+ por uso de RAM.

## 2) Instalar Ollama

1. Descarga e instala Ollama para Windows:
   - https://ollama.com/download/windows
2. Verifica instalacion:

```powershell
ollama --version
```

3. Descarga un modelo ligero:

```powershell
ollama pull qwen2.5:1.5b-instruct
```

4. Prueba rapida:

```powershell
ollama run qwen2.5:1.5b-instruct "hola"
```

## 3) Integracion en este proyecto

El proyecto ya quedo preparado para modo local por defecto.

Valores esperados:
- Proveedor: `ollama`
- Endpoint local: `http://127.0.0.1:11434/api/chat`
- Modelo inicial: `qwen2.5:1.5b-instruct`
- Modo offline estricto: activado

Comandos de voz/texto agregados:
- `modo local`
- `modo nube`
- `modelo ia qwen2.5:1.5b-instruct`

## 4) Privacidad (recomendado)

Para mantener todo local:

1. No uses API keys de nube en el flujo normal.
2. Deja `modo local` activo.
3. Mantener endpoint en `127.0.0.1`.
4. No conectar servicios externos al asistente.

## 5) Voz local (siguiente paso)

Ahora mismo el reconocimiento usa Google Speech API (en linea).
Si quieres privacidad total, migra a STT local:

- Opcion ligera: Vosk
- Opcion mayor calidad: faster-whisper (modelo tiny/base)

TTS local recomendado:
- Piper

## 6) Diagnostico rapido

Si la IA no responde:

```powershell
ollama list
curl http://127.0.0.1:11434/api/tags
```

Pruebas desde la mascota (voz o texto):

- `modo local`
- `estado ia local`
- `probar ia local`
- `modelo ia qwen2.5:1.5b-instruct`

Si `probar ia local` devuelve texto, la integracion mascota + Ollama quedo operativa.

Notas sobre respuestas raras del modelo:

- Algunas salidas contradictorias (por ejemplo, "no puedo hablar espanol" y luego responde en espanol) son un comportamiento del modelo, no de tu microfono.
- Suele pasar por instrucciones internas del modelo, cuantizacion o redaccion de seguridad heredada.
- Para mitigarlo: usa prompts mas directos y en espanol, y prueba modelos alternativos ligeros (`gemma2:2b`, `tinyllama`) para comparar consistencia.

Si el modelo tarda mucho:
- Usa `tinyllama` o reduce carga del sistema.
- Cierra apps pesadas.
- Evita contextos largos en paralelo.

## 7) Notas de seguridad

- Aunque el modelo sea local, una automatizacion puede modificar archivos.
- Mantener permisos por niveles en el asistente (query/files/full).
- Para tareas sensibles, agregar confirmaciones explicitas antes de ejecutar.

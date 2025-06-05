import os
import re
import json
import time
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client as TwilioClient
from retell import Retell

# ------------------------------
# Configuración de logging
# ------------------------------
log_directory = Path("logs")
log_directory.mkdir(exist_ok=True)
log_filename = log_directory / f"retell_system_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)
logger.info("Iniciando sistema de llamadas Retell AI con Twilio (FastAPI)")

# ------------------------------
# FastAPI y CORS
# ------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Montar carpeta 'static/' para servir el HTML
# ------------------------------
# Al montar con html=True, cualquier acceso a '/' devolverá static/index.html automáticamente
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ------------------------------
# Regex para formato E.164
# ------------------------------
E164_REGEX = re.compile(r"^\+\d{10,15}$")

# ------------------------------
# Variables de entorno / Configuración
# ------------------------------
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "tu_account_sid_aqui")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "tu_auth_token_aqui")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "+1TuNumeroTwilioAquí")
TWILIO_WEBHOOK_BASE = os.environ.get("TWILIO_WEBHOOK_BASE")  # Ej: "https://abcd1234.ngrok.io"

RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "tu_retell_api_key_aqui")
RETELL_WEBHOOK_URL = os.environ.get("RETELL_WEBHOOK_URL", "https://abcd1234.ngrok.io/retell-webhook")

logger.info(f"TWILIO_ACCOUNT_SID configurado: {TWILIO_ACCOUNT_SID[:4]}{'*'*10}")
logger.info(f"TWILIO_FROM_NUMBER configurado: {TWILIO_FROM_NUMBER}")
logger.info(f"RETELL_API_KEY configurado: {RETELL_API_KEY[:4] if RETELL_API_KEY else None}{'*'*10}")
logger.info(f"RETELL_WEBHOOK_URL configurado: {RETELL_WEBHOOK_URL}")
logger.info(f"TWILIO_WEBHOOK_BASE configurado: {TWILIO_WEBHOOK_BASE}")

# ------------------------------
# Inicializar clientes
# ------------------------------
try:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Cliente de Twilio inicializado correctamente")
except Exception as e:
    logger.error(f"Error al inicializar el cliente de Twilio: {e}")
    twilio_client = None

try:
    retell_client = Retell(api_key=RETELL_API_KEY)
    logger.info("Cliente de Retell AI inicializado correctamente")
except Exception as e:
    logger.error(f"Error al inicializar el cliente de Retell AI: {e}")
    retell_client = None

# ------------------------------
# Almacenamiento en memoria de transcripciones
# ------------------------------
call_transcriptions = {}

# ------------------------------
# Función para registrar llamada en Retell AI
# ------------------------------
def register_call_with_retell(call_sid: str, from_number: str, to_number: str) -> str | None:
    """
    Registra una llamada en Retell AI mediante SDK y devuelve el call_id.
    """
    if not retell_client:
        logger.error("Cliente de Retell AI no inicializado")
        return None

    payload = {
        "from_number": from_number,
        "to_number": to_number,
        "telephony_identifier": {"twilio_call_sid": call_sid},
    }

    logger.info("Registrando llamada en Retell AI mediante SDK")
    logger.debug(f"Payload Retell SDK: {json.dumps(payload, indent=2)}")
    try:
        response = retell_client.call.create_phone_call(**payload)
        call_id = response.call_id
        logger.info(f"Llamada registrada en Retell. call_id: {call_id}")
        return call_id
    except Exception as e:
        logger.error(f"Error al registrar llamada en Retell AI: {e}")
        return None

# ------------------------------
# Endpoint para iniciar llamada saliente
# ------------------------------
@app.post("/make-call")
async def make_outbound_call(request: Request):
    """
    Inicia una llamada saliente a través de Twilio y la registra en Retell AI.
    """
    payload = await request.json()
    logger.debug(f"Payload /make-call: {json.dumps(payload, indent=2)}")

    to_number = payload.get("to_number")
    from_number = payload.get("from_number", TWILIO_FROM_NUMBER)

    if not to_number:
        logger.error("No se proporcionó 'to_number'")
        raise HTTPException(status_code=400, detail="Se requiere el número de destino")
    if not E164_REGEX.match(to_number):
        logger.error(f"Número destino no en E.164: {to_number}")
        raise HTTPException(status_code=400, detail="Número destino no válido. Debe usar +[código país][número]")
    if not E164_REGEX.match(from_number):
        logger.error(f"'from_number' no en E.164: {from_number}")
        raise HTTPException(status_code=400, detail="Número de origen no válido. Debe usar +[código país][número]")

    logger.info(f"Preparando llamada To: {to_number}, From: {from_number}")

    if not twilio_client:
        logger.error("Cliente de Twilio no inicializado")
        raise HTTPException(status_code=500, detail="Cliente de Twilio no inicializado")

    # Construir webhook_url
    if TWILIO_WEBHOOK_BASE:
        webhook_url = f"{TWILIO_WEBHOOK_BASE}/twilio-webhook"
    else:
        base = str(request.base_url).rstrip("/")
        webhook_url = f"{base}/twilio-webhook"
        logger.warning(
            "TWILIO_WEBHOOK_BASE no configurado. Usando request.base_url. "
            "Asegúrate de usar HTTPS en producción."
        )

    logger.info(f"Webhook URL para Twilio: {webhook_url}")

    try:
        call = twilio_client.calls.create(to=to_number, from_=from_number, url=webhook_url)
        logger.info(f"Llamada iniciada correctamente. CallSid: {call.sid}")
        return JSONResponse({"success": True, "call_sid": call.sid})
    except Exception as e:
        logger.error(f"Error Twilio al crear llamada: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------
# Endpoint Twilio Webhook
# ------------------------------
@app.post("/twilio-webhook")
async def handle_twilio_webhook(request: Request):
    """
    Maneja el webhook de Twilio: registra la llamada en Retell AI y responde con TwiML para Media Streams.
    """
    form = await request.form()
    call_sid = form.get("CallSid")
    from_number = form.get("From")
    to_number = form.get("To")

    logger.info(f"Webhook Twilio recibido. CallSid: {call_sid}, From: {from_number}, To: {to_number}")
    response = VoiceResponse()

    # Registrar llamada en Retell
    retell_call_id = register_call_with_retell(call_sid, from_number, to_number)
    if not retell_call_id:
        logger.error("No se obtuvo call_id de Retell AI; devolviendo TwiML vacío")
        return Response(content=str(response), media_type="text/xml")

    # Construir WebSocket URL
    websocket_url = f"wss://api.retellai.com/voice/websocket/{retell_call_id}"
    logger.info(f"URL de WebSocket para Media Streams: {websocket_url}")

    try:
        connect = Connect()
        connect.stream(url=websocket_url)
        response.append(connect)
        logger.info("Stream de Twilio configurado correctamente")
    except Exception as e:
        logger.error(f"Error al configurar <Connect><Stream> en TwiML: {e}")

    # Inicializar transcripción en memoria
    call_transcriptions[call_sid] = {
        "retell_call_id": retell_call_id,
        "transcription": [],
        "complete": False,
        "start_time": datetime.now().isoformat(),
    }
    logger.info(f"Información de la llamada guardada en memoria. CallSid: {call_sid}")

    return Response(content=str(response), media_type="text/xml")

# ------------------------------
# Endpoint Retell Webhook
# ------------------------------
@app.post("/retell-webhook")
async def handle_retell_webhook(request: Request):
    """
    Maneja los eventos de Retell AI (fragmentos de transcripción y fin de llamada).
    """
    data = await request.json()
    logger.debug(f"Datos recibidos de Retell: {json.dumps(data, indent=2)}")

    call_id = data.get("call_id")
    if not call_id:
        logger.error("No se recibió 'call_id' en el webhook de Retell")
        raise HTTPException(status_code=400, detail="No call_id provided")

    # Buscar el CallSid asociado
    call_sid = None
    for sid, info in call_transcriptions.items():
        if info["retell_call_id"] == call_id:
            call_sid = sid
            break

    logger.info(f"CallSid de Twilio asociado a call_id={call_id}: {call_sid}")

    if call_sid:
        if data.get("interaction_type") == "transcript":
            logger.info("Procesando fragmento tipo 'transcript'")
            transcript = data.get("transcript", [])
            logger.debug(f"Fragmento de transcripción: {json.dumps(transcript, indent=2)}")
            for entry in transcript:
                call_transcriptions[call_sid]["transcription"].append({
                    "role": entry.get("role"),
                    "content": entry.get("content"),
                    "timestamp": time.time(),
                })
                logger.info(
                    f"Entrada de transcripción añadida. Rol: {entry.get('role')}, "
                    f"Contenido: {entry.get('content')[:50]}..."
                )
        if data.get("event") == "call_ended":
            logger.info(f"Llamada finalizada por Retell. CallSid: {call_sid}")
            call_transcriptions[call_sid]["complete"] = True
            call_transcriptions[call_sid]["end_time"] = datetime.now().isoformat()
            save_transcription(call_sid)
    else:
        logger.warning(f"No se encontró CallSid para call_id={call_id}")

    # Responder a Retell
    response_payload = {"response_id": data.get("response_id", 0)}
    logger.info(f"Devolviendo respuesta a Retell: {json.dumps(response_payload)}")
    return JSONResponse(response_payload)

# ------------------------------
# Guardar transcripción en disco
# ------------------------------
def save_transcription(call_sid: str):
    """
    Guarda la transcripción completa en JSON y TXT cuando la llamada finaliza.
    """
    logger.info(f"Guardando transcripción para CallSid: {call_sid}")
    info = call_transcriptions.get(call_sid)
    if not info or not info.get("complete"):
        logger.warning(f"No se puede guardar transcripción. Llamada no completa: {call_sid}")
        return

    transcription = info.get("transcription", [])
    if not transcription:
        logger.warning(f"Transcripción vacía para CallSid: {call_sid}, no se crea archivo")
        return

    transcriptions_dir = Path("transcriptions")
    transcriptions_dir.mkdir(exist_ok=True)

    # Guardar JSON
    json_path = transcriptions_dir / f"{call_sid}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4, ensure_ascii=False)
        logger.info(f"Transcripción guardada en JSON: {json_path}")
    except Exception as e:
        logger.error(f"Error al guardar JSON: {e}")

    # Guardar TXT
    txt_path = transcriptions_dir / f"{call_sid}.txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            for entry in transcription:
                f.write(f"{entry['role']}: {entry['content']}\n")
        logger.info(f"Transcripción guardada en TXT: {txt_path}")
    except Exception as e:
        logger.error(f"Error al guardar TXT: {e}")

# ------------------------------
# Obtener transcripción (polling)
# ------------------------------
@app.get("/get-transcription/{call_sid}")
async def get_transcription(call_sid: str):
    """
    Devuelve la transcripción (JSON) de la llamada identificada por call_sid.
    """
    logger.info(f"Solicitud para obtener transcripción. CallSid: {call_sid}")
    json_path = Path("transcriptions") / f"{call_sid}.json"

    if json_path.exists():
        try:
            return FileResponse(str(json_path), media_type="application/json")
        except Exception as e:
            logger.error(f"Error al leer archivo JSON: {e}")
            raise HTTPException(status_code=500, detail="Error al leer archivo de transcripción")

    # Si no existe en disco, devolver estado en memoria
    info = call_transcriptions.get(call_sid)
    if info:
        is_complete = info.get("complete", False)
        transcription = info.get("transcription", [])
        logger.info(f"Transcripción en memoria. Estado: {'Completa' if is_complete else 'En progreso'}")
        return JSONResponse({"success": True, "transcription": transcription, "is_complete": is_complete})

    logger.warning(f"Transcripción no encontrada para CallSid: {call_sid}")
    raise HTTPException(status_code=404, detail="Transcripción no encontrada")

# ------------------------------
# Listar todas las transcripciones guardadas
# ------------------------------
@app.get("/list-transcriptions")
async def list_transcriptions():
    """
    Lista todos los CallSid que tienen transcripciones guardadas en disco.
    """
    logger.info("Solicitud para listar transcripciones disponibles")
    transcriptions_dir = Path("transcriptions")
    transcriptions_dir.mkdir(exist_ok=True)
    call_sids = [f.stem for f in transcriptions_dir.glob("*.json")]
    logger.info(f"Transcripciones encontradas: {len(call_sids)}")
    return JSONResponse({"success": True, "call_sids": call_sids})

# ------------------------------
# Health check
# ------------------------------
@app.get("/health")
async def health_check():
    """
    Verifica el estado del sistema.
    """
    logger.info("Verificación de estado del sistema (/health)")
    health_status = {
        "status": "up",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "twilio_client": twilio_client is not None,
        "retell_client": retell_client is not None,
        "transcriptions_count": len(call_transcriptions),
        "active_calls": sum(1 for info in call_transcriptions.values() if not info["complete"]),
    }
    logger.info(f"Estado del sistema: {json.dumps(health_status, indent=2)}")
    return JSONResponse(health_status)

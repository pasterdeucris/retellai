from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
import uvicorn
from fpdf import FPDF
from datetime import datetime
import os
import tempfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging
import sys
from logging.handlers import RotatingFileHandler
import time
from fastapi import Request
import unicodedata
import re

# Configuración de logging
def setup_logging():
    """Configura el sistema de logging"""
    # Crear directorio de logs si no existe
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar el logger principal
    logger = logging.getLogger("call_analysis")
    logger.setLevel(logging.INFO)
    
    # Evitar duplicar handlers si ya existen
    if logger.handlers:
        return logger
    
    # Formato de logs
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para archivo (rotativo)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "call_analysis.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Agregar handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Inicializar logger
logger = setup_logging()

app = FastAPI(title="Call Analysis API", version="1.0.0")

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log de request entrante
    logger.info(f"🌐 {request.method} {request.url.path} | Client: {request.client.host if request.client else 'Unknown'}")
    
    # Procesar request
    response = await call_next(request)
    
    # Calcular tiempo de procesamiento
    process_time = time.time() - start_time
    
    # Log de respuesta
    logger.info(f"✅ {request.method} {request.url.path} | Status: {response.status_code} | Time: {process_time:.3f}s")
    
    return response

# Log de inicio del sistema
logger.info("🚀 Call Analysis API iniciada - Version 1.0.0")

# Modelos Pydantic para validar el JSON
class Word(BaseModel):
    word: str
    start: float
    end: float

class TranscriptItem(BaseModel):
    role: str
    content: str
    words: List[Word]
    metadata: Optional[Dict[str, Any]] = None

class CallAnalysis(BaseModel):
    call_summary: str
    in_voicemail: bool
    user_sentiment: str
    call_successful: bool
    custom_analysis_data: Dict[str, Any]

class Call(BaseModel):
    call_id: str
    call_type: str
    agent_id: str
    agent_version: int
    agent_name: Optional[str] = None  # Nuevo campo agregado
    collected_dynamic_variables: Optional[Dict[str, Any]] = None  # Nuevo campo agregado
    call_status: str
    start_timestamp: int
    end_timestamp: int
    duration_ms: int
    transcript: str
    transcript_object: List[TranscriptItem]
    transcript_with_tool_calls: List[TranscriptItem]
    recording_url: str
    public_log_url: str
    disconnection_reason: str
    latency: Dict[str, Any]
    call_cost: Dict[str, Any]
    call_analysis: CallAnalysis
    opt_out_sensitive_data_storage: bool
    opt_in_signed_url: bool
    llm_token_usage: Dict[str, Any]
    access_token: str

class CallEvent(BaseModel):
    event: str
    call: Call

class EmailRequest(BaseModel):
    email: EmailStr
    subject: Optional[str] = "Call Analysis Report"
    message: Optional[str] = "Please find attached the call analysis report."

# Configuración de email (puedes usar variables de entorno)
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",  
    "smtp_port": 587,
    "email_user": "aensilesqla@gmail.com", 
    "email_password": "qpjntndxixwxdahn",
    "default_recipient": "aensilesqla@gmail.com",  # Email por defecto
}

def clean_text_for_pdf(text):
    """
    Limpia el texto para que sea compatible con FPDF
    Reemplaza caracteres Unicode problemáticos con equivalentes ASCII
    """
    if not text:
        return ""
    
    # Convertir a string si no lo es
    text = str(text)
    
    # Mapeo de caracteres problemáticos comunes
    char_replacements = {
        ''': "'",  # Smart quote left
        ''': "'",  # Smart quote right
        '"': '"',  # Smart quote left double
        '"': '"',  # Smart quote right double
        '–': '-',  # En dash
        '—': '-',  # Em dash
        '…': '...',  # Ellipsis
        '°': ' degrees',  # Degree symbol
        '©': '(c)',  # Copyright
        '®': '(R)',  # Registered trademark
        '™': '(TM)',  # Trademark
        '€': 'EUR',  # Euro symbol
        '£': 'GBP',  # Pound symbol
        '¥': 'JPY',  # Yen symbol
        '§': 'Section',  # Section symbol
        '¶': 'Paragraph',  # Paragraph symbol
        '†': '+',  # Dagger
        '‡': '++',  # Double dagger
        '•': '*',  # Bullet
        '‰': ' per mille',  # Per mille
        '‹': '<',  # Single left angle quotation
        '›': '>',  # Single right angle quotation
        '«': '<<',  # Left double angle quotation
        '»': '>>',  # Right double angle quotation
    }
    
    # Aplicar reemplazos específicos
    for unicode_char, ascii_replacement in char_replacements.items():
        text = text.replace(unicode_char, ascii_replacement)
    
    # Normalizar Unicode y remover acentos si es necesario
    # NFD = Normalization Form Decomposed
    text = unicodedata.normalize('NFD', text)
    
    # Filtrar solo caracteres ASCII imprimibles y algunos especiales
    allowed_chars = []
    for char in text:
        # Permitir caracteres ASCII imprimibles (32-126)
        if 32 <= ord(char) <= 126:
            allowed_chars.append(char)
        # Permitir algunos caracteres especiales comunes
        elif char in ['\n', '\r', '\t']:
            allowed_chars.append(char)
        # Reemplazar otros caracteres con espacio
        else:
            # Solo agregar espacio si el último carácter no es espacio
            if allowed_chars and allowed_chars[-1] != ' ':
                allowed_chars.append(' ')
    
    cleaned_text = ''.join(allowed_chars)
    
    # Limpiar espacios múltiples
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text

def safe_text_length(text, max_length=80):
    """
    Trunca texto de manera segura para evitar problemas de ancho
    """
    cleaned = clean_text_for_pdf(text)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length-3] + "..."

def send_email_with_pdf(pdf_path: str, recipient_email: str, subject: str, message: str, call_id: str):
    """
    Envía un email con el PDF adjunto
    """
    logger.info(f"📧 Iniciando envío de email | Call ID: {call_id} | Destinatario: {recipient_email}")
    
    try:
        # Verificar que el archivo PDF existe
        if not os.path.exists(pdf_path):
            logger.error(f"❌ PDF no encontrado: {pdf_path}")
            return False
        
        pdf_size = os.path.getsize(pdf_path)
        logger.info(f"📎 PDF encontrado | Tamaño: {pdf_size} bytes | Ruta: {pdf_path}")
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["email_user"]
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        logger.info(f"✉️ Construyendo mensaje | De: {EMAIL_CONFIG['email_user']} | Para: {recipient_email}")
        
        # Cuerpo del mensaje HTML
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                        <h1 style="margin: 0; font-size: 28px;">📞 Call Analysis Report</h1>
                        <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">
                            Complete analysis for Call ID: {call_id}
                        </p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                        <p style="font-size: 16px; margin-bottom: 20px;">{message}</p>
                        
                        <div style="background: white; padding: 20px; border-radius: 8px; 
                                    border-left: 4px solid #667eea; margin: 20px 0;">
                            <h3 style="color: #667eea; margin-top: 0;">📊 Report Contents:</h3>
                            <ul style="margin: 0; padding-left: 20px;">
                                <li>Success, Engagement & Sentiment Scores</li>
                                <li>Complete call information and statistics</li>
                                <li>Full conversation transcript in chat format</li>
                                <li>Cost analysis and billing details</li>
                            </ul>
                        </div>
                        
                        <p style="color: #666; font-size: 14px; margin-top: 30px;">
                            This report was automatically generated on {datetime.now().strftime("%Y-%m-%d at %H:%M:%S")}
                        </p>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center;">
                            <p style="color: #888; font-size: 12px; margin: 0;">
                                Call Analysis System | Powered by FastAPI
                            </p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        logger.info("📝 Cuerpo HTML del email construido")
        
        # Adjuntar PDF
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        
        pdf_filename = f"call_analysis_{call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {pdf_filename}'
        )
        
        msg.attach(part)
        logger.info(f"📎 PDF adjuntado como: {pdf_filename}")
        
        # Conectar al servidor SMTP
        logger.info(f"🔗 Conectando a servidor SMTP: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        logger.info("🔐 Conexión TLS establecida")
        
        server.login(EMAIL_CONFIG["email_user"], EMAIL_CONFIG["email_password"])
        logger.info("✅ Login SMTP exitoso")
        
        # Enviar email
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG["email_user"], recipient_email, text)
        server.quit()
        
        logger.info(f"✅ Email enviado exitosamente | Call ID: {call_id} | Destinatario: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ Error de autenticación SMTP | Call ID: {call_id} | Error: {str(e)}")
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f"❌ Error de conexión SMTP | Call ID: {call_id} | Error: {str(e)}")
        return False
    except FileNotFoundError as e:
        logger.error(f"❌ Archivo PDF no encontrado | Call ID: {call_id} | Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error general enviando email | Call ID: {call_id} | Error: {str(e)}")
        return False

# Función para concatenar la conversación
def concatenate_conversation(transcript_object: List[TranscriptItem]) -> str:
    """
    Concatena la conversación en un formato legible
    """
    logger.info(f"🔄 Concatenando conversación | Total elementos: {len(transcript_object)}")
    
    conversation = []
    
    for i, item in enumerate(transcript_object):
        role = item.role.capitalize()
        content = item.content
        
        # Formato: "Rol: Contenido"
        conversation.append(f"{role}: {content}")
        logger.debug(f"Elemento {i+1}: {role} - {len(content)} caracteres")
    
    result = "\n".join(conversation)
    logger.info(f"✅ Conversación concatenada | Total líneas: {len(conversation)} | Caracteres: {len(result)}")
    
    return result

class ModernPDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        # Header moderno con línea decorativa
        self.set_fill_color(79, 70, 229)  # Púrpura moderno
        self.rect(0, 0, 210, 8, 'F')
        
        self.set_font('Arial', 'B', 18)
        self.set_text_color(51, 51, 51)
        self.ln(15)
        self.cell(0, 12, 'Call Analysis Report', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cell(0, 10, f'Generated on {current_time} | Page {self.page_no()}', 0, 0, 'C')
    
    def safe_cell(self, w, h, txt='', border=0, ln=0, align='', fill=False):
        """
        Versión segura de cell que limpia el texto antes de usarlo
        """
        cleaned_txt = clean_text_for_pdf(txt)
        self.cell(w, h, cleaned_txt, border, ln, align, fill)
    
    def safe_multi_cell(self, w, h, txt, border=0, align='J', fill=False):
        """
        Versión segura de multi_cell que limpia el texto
        """
        cleaned_txt = clean_text_for_pdf(txt)
        self.multi_cell(w, h, cleaned_txt, border, align, fill)
    
    def add_metric_card(self, title, value, status, x_pos, width=60):
        """Crea una tarjeta de métrica moderna"""
        y_start = self.get_y()
        
        # Limpiar textos
        title = clean_text_for_pdf(title)
        value = clean_text_for_pdf(str(value))
        status = clean_text_for_pdf(status)
        
        # Determinar color según status
        if status == "GOOD":
            bg_color = (34, 197, 94)  # Verde
            text_color = (255, 255, 255)
        elif status == "OKAY":
            bg_color = (251, 146, 60)  # Naranja
            text_color = (255, 255, 255)
        else:
            bg_color = (239, 68, 68)  # Rojo
            text_color = (255, 255, 255)
        
        # Fondo de la tarjeta
        self.set_fill_color(*bg_color)
        self.rect(x_pos, y_start, width, 25, 'F')
        
        # Título de la métrica
        self.set_xy(x_pos + 5, y_start + 3)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(*text_color)
        self.cell(width-10, 6, title, 0, 0, 'L')
        
        # Valor grande
        self.set_xy(x_pos + 5, y_start + 10)
        self.set_font('Arial', 'B', 16)
        self.cell(width-30, 8, value, 0, 0, 'L')
        
        # Status
        self.set_xy(x_pos + width - 25, y_start + 12)
        self.set_font('Arial', 'B', 8)
        self.cell(20, 6, status, 0, 0, 'R')
        
        return y_start + 30
    
    def add_section_title(self, title, icon=""):
        self.ln(8)
        self.set_font('Arial', 'B', 14)
        self.set_text_color(51, 51, 51)
        
        # Limpiar título e icono
        title = clean_text_for_pdf(title)
        icon = clean_text_for_pdf(icon)
        
        full_title = f"{icon} {title}" if icon else title
        self.safe_cell(0, 10, full_title, 0, 1, 'L')
        
        # Línea decorativa debajo del título
        self.set_fill_color(229, 231, 235)
        self.rect(10, self.get_y(), 190, 1, 'F')
        self.ln(5)
    
    def add_info_grid(self, data, cols=2):
        """Crea una grilla de información moderna"""
        self.set_font('Arial', '', 10)
        
        for i, (key, value) in enumerate(data):
            x_pos = 15 if i % cols == 0 else 110
            if i % cols == 0 and i > 0:
                self.ln(12)
            
            y_pos = self.get_y()
            
            # Fondo suave para la celda
            self.set_fill_color(248, 250, 252)
            self.rect(x_pos, y_pos, 85, 10, 'F')
            
            # Limpiar key y value
            clean_key = safe_text_length(str(key), 25)
            clean_value = safe_text_length(str(value), 25)
            
            # Clave en gris
            self.set_xy(x_pos + 2, y_pos + 1)
            self.set_font('Arial', '', 8)
            self.set_text_color(107, 114, 128)
            self.safe_cell(83, 4, clean_key, 0, 0, 'L')
            
            # Valor en negro
            self.set_xy(x_pos + 2, y_pos + 5)
            self.set_font('Arial', 'B', 9)
            self.set_text_color(31, 41, 55)
            self.safe_cell(83, 4, clean_value, 0, 0, 'L')
        
        self.ln(15)
    
    def add_summary_box(self, text):
        """Caja de resumen con texto limpio"""
        # Limpiar el texto del resumen
        clean_summary = clean_text_for_pdf(text)
        
        # Calcular altura basada en el texto limpio
        words_per_line = 70
        estimated_lines = max(3, len(clean_summary) // words_per_line + 1)
        box_height = max(30, estimated_lines * 5 + 15)
        
        # Fondo de la caja
        self.set_fill_color(249, 250, 251)
        self.rect(15, self.get_y(), 180, box_height, 'F')
        
        # Borde izquierdo decorativo
        self.set_fill_color(79, 70, 229)
        self.rect(15, self.get_y(), 4, box_height, 'F')
        
        # Texto del resumen
        self.set_xy(25, self.get_y() + 5)
        self.set_font('Arial', '', 10)
        self.set_text_color(55, 65, 81)
        
        # Usar multi_cell para texto largo
        try:
            self.safe_multi_cell(170, 5, clean_summary, 0, 'L')
        except Exception as e:
            logger.warning(f"Error en summary box, usando texto truncado: {str(e)}")
            # Fallback: usar versión truncada
            truncated = safe_text_length(clean_summary, 300)
            self.safe_multi_cell(170, 5, truncated, 0, 'L')
        
        self.ln(10)
    
    def add_conversation_modern(self, conversation):
        """Formato moderno para la conversación con texto limpio"""
        clean_conversation = clean_text_for_pdf(conversation)
        lines = clean_conversation.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            try:
                if line.startswith('User:'):
                    self._add_message_bubble(line[5:].strip(), 'USER', (219, 234, 254), (30, 64, 175))
                elif line.startswith('Agent:'):
                    self._add_message_bubble(line[6:].strip(), 'AGENT', (220, 252, 231), (22, 101, 52))
                elif line.startswith('Assistant:'):
                    self._add_message_bubble(line[10:].strip(), 'AGENT', (220, 252, 231), (22, 101, 52))
                else:
                    # Línea sin formato específico
                    self._add_message_bubble(line.strip(), 'SYSTEM', (243, 244, 246), (75, 85, 99))
            except Exception as e:
                logger.warning(f"Error procesando línea de conversación: {str(e)}")
                continue
    
    def _add_message_bubble(self, message, sender, bg_color, text_color):
        """Añade una burbuja de mensaje individual"""
        if not message.strip():
            return
            
        # Limpiar mensaje
        clean_message = safe_text_length(message, 200)
        
        self.ln(3)
        
        # Calcular altura necesaria
        words_per_line = 60
        estimated_lines = max(1, len(clean_message) // words_per_line + 1)
        msg_height = max(8, estimated_lines * 4 + 8)
        
        # Verificar que no se sale de la página
        if self.get_y() + msg_height > 280:  # Cerca del final de la página
            self.add_page()
        
        # Fondo del mensaje
        self.set_fill_color(*bg_color)
        self.rect(20, self.get_y(), 160, msg_height, 'F')
        
        # Etiqueta del remitente
        self.set_xy(25, self.get_y() + 1)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(*text_color)
        self.safe_cell(0, 3, sender, 0, 1, 'L')
        
        # Mensaje
        self.set_x(25)
        self.set_font('Arial', '', 9)
        self.set_text_color(51, 51, 51)
        
        try:
            # Usar multi_cell para mensajes largos
            if len(clean_message) > 80:
                self.safe_multi_cell(150, 4, clean_message, 0, 'L')
            else:
                self.safe_cell(150, 4, clean_message, 0, 1, 'L')
        except Exception as e:
            logger.warning(f"Error añadiendo mensaje, usando versión simple: {str(e)}")
            # Fallback simple
            simple_message = safe_text_length(clean_message, 80)
            self.safe_cell(150, 4, simple_message, 0, 1, 'L')

def generate_pdf_report(call: Call, concatenated_conversation: str, conversation_summary: Dict[str, Any], output_path: str):
    """
    Genera un PDF moderno con manejo robusto de Unicode
    """
    logger.info(f"📄 Iniciando generación de PDF con soporte Unicode | Call ID: {call.call_id}")
    
    try:
        pdf = ModernPDFReport()
        pdf.add_page()
        
        # Calcular métricas para el dashboard
        success_score = 85 if call.call_analysis.call_successful else 45
        engagement_score = max(20, 100 - (conversation_summary['inaudible_speeches'] * 30))
        
        # Mapear sentiment a score
        sentiment_map = {
            "Positive": 90,
            "Neutral": 70, 
            "Negative": 40
        }
        sentiment_score = sentiment_map.get(call.call_analysis.user_sentiment, 70)
        
        logger.info(f"📊 Métricas calculadas | Success: {success_score} | Engagement: {engagement_score} | Sentiment: {sentiment_score}")
        
        # Dashboard de métricas en la parte superior
        pdf.ln(5)
        
        # Métricas principales en tarjetas
        y_pos = pdf.add_metric_card("Success Score", success_score, 
                                   "GOOD" if success_score >= 70 else "OKAY" if success_score >= 50 else "POOR", 
                                   15, 60)
        
        pdf.set_y(y_pos - 25)
        pdf.add_metric_card("Engagement", engagement_score,
                           "GOOD" if engagement_score >= 80 else "OKAY" if engagement_score >= 60 else "POOR",
                           80, 60)
        
        pdf.set_y(y_pos - 25)
        pdf.add_metric_card("Sentiment", sentiment_score,
                           "GOOD" if sentiment_score >= 80 else "OKAY" if sentiment_score >= 60 else "POOR",
                           145, 60)
        
        pdf.set_y(y_pos + 5)
        logger.info("✅ Tarjetas de métricas agregadas al PDF")
        
        # Resumen ejecutivo con texto limpio
        pdf.add_section_title("Summary")
        pdf.add_summary_box(call.call_analysis.call_summary)
        logger.info("✅ Sección de resumen agregada")
        
        # Información de la llamada en grid moderno
        pdf.add_section_title("Call Information")
        
        call_info = [
            ("Call ID", safe_text_length(call.call_id, 15)),
            ("Status", call.call_status.upper()),
            ("Duration", f"{call.duration_ms / 1000:.1f}s"),
            ("Date", datetime.fromtimestamp(call.start_timestamp / 1000).strftime("%Y-%m-%d")),
            ("Time", datetime.fromtimestamp(call.start_timestamp / 1000).strftime("%H:%M:%S")),
            ("Type", call.call_type.replace("_", " ").title()),
            ("Agent ID", safe_text_length(call.agent_id, 12)),
            ("End Reason", call.disconnection_reason.replace("_", " ").title())
        ]
        
        pdf.add_info_grid(call_info, 2)
        logger.info("✅ Información de llamada agregada")
        
        # Estadísticas de conversación
        pdf.add_section_title("Conversation Stats")
        
        stats_info = [
            ("Total Messages", conversation_summary['total_exchanges']),
            ("User Messages", conversation_summary['user_messages']),
            ("Agent Messages", conversation_summary['agent_messages']),
            ("Inaudible Count", conversation_summary['inaudible_speeches']),
            ("Success Rate", "Yes" if call.call_analysis.call_successful else "No"),
            ("Voicemail", "Yes" if call.call_analysis.in_voicemail else "No")
        ]
        
        pdf.add_info_grid(stats_info, 2)
        logger.info("✅ Estadísticas de conversación agregadas")
        
        # Nueva página para la transcripción
        pdf.add_page()
        pdf.add_section_title("Full Transcript")
        pdf.add_conversation_modern(concatenated_conversation)
        logger.info("✅ Transcripción completa agregada")
        
        # Información de costos al final
        pdf.ln(10)
        pdf.add_section_title("Cost Analysis")
        
        cost_info = [
            ("Total Cost", f"${call.call_cost.get('combined_cost', 0):.3f}"),
            ("Billed Duration", f"{call.call_cost.get('total_duration_seconds', 0)}s"),
            ("Rate per Unit", f"${call.call_cost.get('total_duration_unit_price', 0):.6f}"),
            ("Currency", "USD")
        ]
        
        pdf.add_info_grid(cost_info, 2)
        logger.info("✅ Análisis de costos agregado")
        
        # Guardar el PDF
        pdf.output(output_path)
        
        # Verificar que el archivo se creó correctamente
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"✅ PDF generado exitosamente con soporte Unicode | Tamaño: {file_size} bytes")
        else:
            logger.error(f"❌ Error: PDF no se creó en la ruta especificada: {output_path}")
            
    except Exception as e:
        logger.error(f"❌ Error generando PDF | Call ID: {call.call_id} | Error: {str(e)}")
        raise

def get_conversation_summary(transcript_object: List[TranscriptItem]) -> Dict[str, Any]:
    """
    Genera un resumen de la conversación con estadísticas
    """
    logger.info(f"📊 Generando resumen de conversación | Total elementos: {len(transcript_object)}")
    
    user_messages = [item for item in transcript_object if item.role == "user"]
    agent_messages = [item for item in transcript_object if item.role == "agent"]
    inaudible_count = len([item for item in user_messages if "(inaudible speech)" in item.content])
    
    summary = {
        "total_exchanges": len(transcript_object),
        "user_messages": len(user_messages),
        "agent_messages": len(agent_messages),
        "inaudible_speeches": inaudible_count
    }
    
    logger.info(f"📈 Resumen generado | Total: {summary['total_exchanges']} | Usuario: {summary['user_messages']} | Agente: {summary['agent_messages']} | Inaudibles: {summary['inaudible_speeches']}")
    
    return summary

@app.get("/")
async def root():
    logger.info("🏠 Endpoint raíz accedido")
    return {"message": "Call Analysis API - Envía un POST a /process-call con el JSON de la llamada"}

@app.post("/auto-email-report")
async def auto_email_report(call_event: CallEvent):
    """
    Genera y envía automáticamente a la dirección configurada por defecto
    SOLO procesa eventos 'call_analyzed' - otros eventos retornan 200
    """
    logger.info(f"📥 Auto-email-report recibido | Evento: {call_event.event} | Call ID: {call_event.call.call_id}")
    
    try:
        # FILTRO: Solo procesar call_analyzed
        if call_event.event != "call_analyzed":
            logger.info(f"⏭️ Evento '{call_event.event}' ignorado - solo se procesan eventos 'call_analyzed'")
            return Response(status_code=200, content={"message": f"Event '{call_event.event}' received but not processed"})
            
        if not EMAIL_CONFIG.get("default_recipient"):
            logger.error("❌ No hay destinatario por defecto configurado")
            raise HTTPException(status_code=400, detail="No default recipient configured. Please set default_recipient in EMAIL_CONFIG")
            
        call = call_event.call
        logger.info(f"🔄 Procesando llamada | ID: {call.call_id} | Status: {call.call_status} | Duración: {call.duration_ms/1000:.1f}s")
                
        # Concatenar la conversación
        logger.info("🔄 Iniciando concatenación de conversación")
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        logger.info(f"📁 Ruta temporal para PDF: {pdf_path}")
        
        # Generar el PDF
        logger.info("🔄 Iniciando generación de PDF")
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email al destinatario por defecto
        logger.info(f"📧 Enviando email a destinatario por defecto: {EMAIL_CONFIG['default_recipient']}")
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=EMAIL_CONFIG["default_recipient"],
            subject="Call Analysis Report - Luna Rossa",
            message="Please find attached the complete call analysis report with metrics and full transcript.",
            call_id=call.call_id
        )
        
        if email_sent:
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ Archivo temporal eliminado: {pdf_path}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo eliminar archivo temporal: {str(e)}")
            
            logger.info(f"✅ Proceso completado exitosamente | Call ID: {call.call_id}")
            return {
                "success": True,
                "message": f"Report generated and sent successfully to {EMAIL_CONFIG['default_recipient']}",
                "call_id": call.call_id,
                "recipient": EMAIL_CONFIG["default_recipient"],
                "call_status": call.call_status,
                "duration_seconds": call.duration_ms / 1000,
                "event_processed": call_event.event
            }
        else:
            logger.error(f"❌ Fallo en envío de email | Call ID: {call.call_id}")
            return {
                "success": False,
                "message": "Report generated but failed to send email",
                "call_id": call.call_id,
                "pdf_path": pdf_path
            }
        
    except Exception as e:
        logger.error(f"❌ Error en auto-email-report | Call ID: {call_event.call.call_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in auto-email: {str(e)}")

@app.post("/email-to-address")
async def email_to_address(call_event: CallEvent, recipient_email: EmailStr):
    """
    Genera PDF y envía a un email específico pasado como query parameter
    SOLO procesa eventos 'call_analyzed' - otros eventos retornan 200
    """
    logger.info(f"📧 Email-to-address recibido | Evento: {call_event.event} | Call ID: {call_event.call.call_id} | Destinatario: {recipient_email}")
    
    try:
        # FILTRO: Solo procesar call_analyzed
        if call_event.event != "call_analyzed":
            logger.info(f"⏭️ Evento '{call_event.event}' ignorado - solo se procesan eventos 'call_analyzed'")
            return Response(status_code=200, content={"message": f"Event '{call_event.event}' received but not processed"})
            
        call = call_event.call
        
        # Solo procesar llamadas que realmente terminaron
        if call.call_status != "ended":
            logger.info(f"⏭️ Call status '{call.call_status}' - no se procesa (esperando 'ended')")
            return Response(status_code=200, content={"message": f"Call status '{call.call_status}' - not processing"})
        
        logger.info(f"🔄 Procesando llamada para email específico | ID: {call.call_id} | Duración: {call.duration_ms/1000:.1f}s")
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        logger.info(f"📁 Generando PDF para envío específico: {pdf_path}")
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email
        logger.info(f"📧 Enviando a email específico: {recipient_email}")
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=recipient_email,
            subject=f"Call Analysis Report - {call.call_id}",
            message="Please find attached the complete call analysis report with success metrics, engagement scores, and full conversation transcript.",
            call_id=call.call_id
        )
        
        # Limpiar
        try:
            os.remove(pdf_path)
            logger.info(f"🗑️ Archivo temporal eliminado: {pdf_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo eliminar archivo temporal: {str(e)}")
            
        result = {
            "success": email_sent,
            "message": f"Email {'sent successfully' if email_sent else 'failed to send'} to {recipient_email}",
            "call_id": call.call_id,
            "recipient": recipient_email,
            "event_processed": call_event.event
        }
        
        if email_sent:
            logger.info(f"✅ Email enviado exitosamente a {recipient_email} | Call ID: {call.call_id}")
        else:
            logger.error(f"❌ Fallo en envío de email a {recipient_email} | Call ID: {call.call_id}")
            
        return result
        
    except Exception as e:
        logger.error(f"❌ Error en email-to-address | Call ID: {call_event.call.call_id} | Destinatario: {recipient_email} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")

@app.post("/send-to-custom-email")
async def send_to_custom_email(call_event: CallEvent, email_config: EmailRequest):
    """
    Genera PDF y envía con configuración de email personalizada (sujeto y mensaje)
    """
    logger.info(f"📧 Send-to-custom-email recibido | Call ID: {call_event.call.call_id} | Destinatario: {email_config.email}")
    
    try:
        call = call_event.call
        
        logger.info(f"🔄 Procesando llamada con configuración personalizada | ID: {call.call_id}")
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        logger.info(f"📁 Generando PDF con configuración personalizada: {pdf_path}")
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email con configuración personalizada
        logger.info(f"📧 Enviando con configuración personalizada | Destinatario: {email_config.email} | Asunto: {email_config.subject}")
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=email_config.email,
            subject=email_config.subject,
            message=email_config.message,
            call_id=call.call_id
        )
        
        # Limpiar archivo temporal
        try:
            os.remove(pdf_path)
            logger.info(f"🗑️ Archivo temporal eliminado: {pdf_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo eliminar archivo temporal: {str(e)}")
        
        if email_sent:
            logger.info(f"✅ Email con configuración personalizada enviado exitosamente | Call ID: {call.call_id}")
            return {
                "success": True,
                "message": f"Report generated and sent successfully to {email_config.email}",
                "call_id": call.call_id,
                "recipient": email_config.email,
                "subject": email_config.subject,
                "email_sent": True
            }
        else:
            logger.error(f"❌ Fallo en envío de email personalizado | Call ID: {call.call_id}")
            return {
                "success": False,
                "message": "Report generated but failed to send email",
                "call_id": call.call_id,
                "email_sent": False,
                "pdf_path": pdf_path
            }
        
    except Exception as e:
        logger.error(f"❌ Error en send-to-custom-email | Call ID: {call_event.call.call_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating/sending custom email: {str(e)}")

@app.post("/webhook")
async def webhook_endpoint(call_event: CallEvent):
    """
    Endpoint para webhooks automáticos
    SOLO procesa 'call_analyzed' - retorna 200 para otros eventos
    """
    logger.info(f"🎣 Webhook recibido | Evento: {call_event.event} | Call ID: {call_event.call.call_id}")
    
    try:
        # FILTRO PRINCIPAL: Solo procesar call_analyzed
        if call_event.event != "call_analyzed":
            logger.info(f"⏭️ Webhook ignorado - Evento '{call_event.event}' no es 'call_analyzed'")
            return Response(status_code=200, content={"message": f"Event '{call_event.event}' received but not processed"})
            
        if not EMAIL_CONFIG.get("default_recipient"):
            # Si no hay destinatario configurado, registrar pero no fallar
            logger.warning(f"⚠️ No hay destinatario por defecto configurado para call {call_event.call.call_id}")
            return Response(status_code=200, content={"message": "No default recipient configured"})
            
        call = call_event.call
        
        # Verificar que la llamada realmente terminó
        if call.call_status != "ended":
            logger.info(f"⏭️ Call status '{call.call_status}' - no se procesa (esperando 'ended')")
            return Response(status_code=200, content={"message": f"Call status '{call.call_status}' - not processing"})
        
        logger.info(f"🔄 Procesando webhook | Call ID: {call.call_id} | Duración: {call.duration_ms/1000:.1f}s | Status: {call.call_status}")
        
        # Procesar automáticamente
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        logger.info(f"📁 Generando PDF en: {pdf_path}")
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email
        logger.info(f"📧 Enviando email automático a: {EMAIL_CONFIG['default_recipient']}")
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=EMAIL_CONFIG["default_recipient"],
            subject="Call Analysis Report - Luna Rossa (Automated)",
            message="Automated call analysis report generated from webhook.",
            call_id=call.call_id
        )
        
        # Limpiar archivo temporal
        try:
            os.remove(pdf_path)
            logger.info(f"🗑️ Archivo temporal eliminado: {pdf_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo eliminar archivo temporal: {str(e)}")
        
        # Log del resultado (para debugging)
        logger.info(f"✅ Webhook procesado exitosamente | Call: {call.call_id} | Email enviado: {email_sent} | Destinatario: {EMAIL_CONFIG['default_recipient']}")
        
        # Retornar 200 OK para confirmar procesamiento
        return {"success": True, "call_id": call.call_id, "email_sent": email_sent}
        
    except Exception as e:
        # Log del error pero no fallar el webhook
        logger.error(f"❌ Error en webhook | Call ID: {call_event.call.call_id} | Error: {str(e)}")
        return Response(status_code=200, content={"error": str(e), "success": False})

@app.post("/update-default-recipient")
async def update_default_recipient(email: EmailStr):
    """
    Actualiza el email destinatario por defecto
    """
    try:
        EMAIL_CONFIG["default_recipient"] = email
        return {
            "success": True,
            "message": f"Default recipient updated to {email}",
            "default_recipient": email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating recipient: {str(e)}")

@app.post("/generate-and-email-report")
async def generate_and_email_report(call_event: CallEvent):
    """
    Genera un PDF completo y lo envía por email al destinatario por defecto
    Recibe directamente el JSON del evento call_analyzed
    """
    logger.info(f"📧 Generate-and-email-report recibido | Evento: {call_event.event} | Call ID: {call_event.call.call_id}")
    
    try:
        # Verificar que hay destinatario configurado
        if not EMAIL_CONFIG.get("default_recipient"):
            logger.error("❌ No hay destinatario por defecto configurado")
            raise HTTPException(status_code=400, detail="No default recipient configured. Please set default_recipient in EMAIL_CONFIG")
        
        call = call_event.call
        
        logger.info(f"🔄 Procesando llamada para reporte | ID: {call.call_id} | Status: {call.call_status} | Duración: {call.duration_ms/1000:.1f}s")
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        
        # Obtener resumen de la conversación
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        logger.info(f"📁 Generando PDF en ruta temporal: {pdf_path}")
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email al destinatario por defecto
        logger.info(f"📧 Enviando reporte a destinatario por defecto: {EMAIL_CONFIG['default_recipient']}")
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=EMAIL_CONFIG["default_recipient"],
            subject=f"Call Analysis Report - {call.call_id}",
            message="Please find attached the complete call analysis report with success metrics, engagement scores, and full conversation transcript.",
            call_id=call.call_id
        )
        
        if email_sent:
            # Limpiar archivo temporal
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ Archivo temporal eliminado: {pdf_path}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo eliminar archivo temporal: {str(e)}")
            
            logger.info(f"✅ Reporte generado y enviado exitosamente | Call ID: {call.call_id}")
            return {
                "success": True,
                "message": f"Report generated and sent successfully to {EMAIL_CONFIG['default_recipient']}",
                "call_id": call.call_id,
                "recipient": EMAIL_CONFIG["default_recipient"],
                "email_sent": True,
                "event_processed": call_event.event,
                "call_details": {
                    "duration_seconds": call.duration_ms / 1000,
                    "status": call.call_status,
                    "sentiment": call.call_analysis.user_sentiment,
                    "successful": call.call_analysis.call_successful
                }
            }
        else:
            logger.error(f"❌ Fallo en envío de email para reporte | Call ID: {call.call_id}")
            return {
                "success": False,
                "message": "Report generated but failed to send email",
                "call_id": call.call_id,
                "email_sent": False,
                "pdf_path": pdf_path  # En caso de error, devolver la ruta para descarga manual
            }
        
    except Exception as e:
        logger.error(f"❌ Error en generate-and-email-report | Call ID: {call_event.call.call_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating/sending report: {str(e)}")

@app.post("/send-existing-pdf")
async def send_existing_pdf(call_event: CallEvent, email: EmailStr, subject: str = "Call Analysis Report"):
    """
    Envía un PDF ya generado por email (para testing o reenvío)
    """
    try:
        call = call_event.call
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Generar PDF temporal
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar email
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=email,
            subject=subject,
            message="Please find attached the call analysis report generated from your request.",
            call_id=call.call_id
        )
        
        # Limpiar
        try:
            os.remove(pdf_path)
        except:
            pass
            
        return {
            "success": email_sent,
            "message": f"Email {'sent successfully' if email_sent else 'failed to send'} to {email}",
            "call_id": call.call_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")

@app.get("/email-config")
async def get_email_config():
    """
    Obtiene la configuración de email actual (sin mostrar credenciales)
    """
    logger.info("📧 Consulta de configuración de email")
    
    config = {
        "smtp_server": EMAIL_CONFIG["smtp_server"],
        "smtp_port": EMAIL_CONFIG["smtp_port"],
        "sender_email": EMAIL_CONFIG["email_user"],
        "default_recipient": EMAIL_CONFIG.get("default_recipient", "Not set"),
        "status": "configured" if EMAIL_CONFIG["email_user"] != "tu_email@gmail.com" else "not_configured"
    }
    
    logger.info(f"📧 Configuración consultada | SMTP: {config['smtp_server']} | Sender: {config['sender_email']} | Recipient: {config['default_recipient']}")
    
    return config

@app.post("/update-email-config")
async def update_email_config(smtp_server: str, smtp_port: int, email_user: str, email_password: str):
    """
    Actualiza la configuración de email SMTP
    """
    logger.info(f"🔧 Actualizando configuración SMTP | Servidor: {smtp_server} | Usuario: {email_user}")
    
    try:
        old_config = f"{EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}"
        
        EMAIL_CONFIG["smtp_server"] = smtp_server
        EMAIL_CONFIG["smtp_port"] = smtp_port
        EMAIL_CONFIG["email_user"] = email_user
        EMAIL_CONFIG["email_password"] = email_password
        
        logger.info(f"✅ Configuración SMTP actualizada | Anterior: {old_config} | Nuevo: {smtp_server}:{smtp_port}")
        
        return {
            "success": True,
            "message": "Email configuration updated successfully",
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "email_user": email_user
        }
    except Exception as e:
        logger.error(f"❌ Error actualizando configuración SMTP | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")

@app.post("/generate-pdf-report")
async def generate_pdf_report_endpoint(call_event: CallEvent):
    """
    Genera un PDF completo con el análisis de la llamada
    """
    try:
        call = call_event.call
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        
        # Obtener resumen de la conversación
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Devolver el archivo PDF
        return FileResponse(
            path=pdf_path,
            filename=pdf_filename,
            media_type='application/pdf'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")

@app.post("/process-call")
async def process_call(call_event: CallEvent):
    """
    Procesa el JSON de la llamada y devuelve la conversación concatenada
    """
    try:
        call = call_event.call
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        
        # Obtener resumen de la conversación
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Preparar respuesta
        response = {
            "call_id": call.call_id,
            "call_status": call.call_status,
            "duration_seconds": call.duration_ms / 1000,
            "conversation_summary": conversation_summary,
            "concatenated_conversation": concatenated_conversation,
            "original_transcript": call.transcript,
            "call_analysis": {
                "summary": call.call_analysis.call_summary,
                "sentiment": call.call_analysis.user_sentiment,
                "successful": call.call_analysis.call_successful,
                "in_voicemail": call.call_analysis.in_voicemail
            }
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando la llamada: {str(e)}")

@app.post("/concatenate-only")
async def concatenate_only(call_event: CallEvent):
    """
    Endpoint simplificado que solo devuelve la conversación concatenada
    """
    logger.info(f"🔗 Concatenate-only recibido | Evento: {call_event.event} | Call ID: {call_event.call.call_id}")
    
    try:
        concatenated = concatenate_conversation(call_event.call.transcript_object)
        
        result = {
            "call_id": call_event.call.call_id,
            "concatenated_conversation": concatenated
        }
        
        logger.info(f"✅ Conversación concatenada exitosamente | Call ID: {call_event.call.call_id} | Caracteres: {len(concatenated)}")
        
        return result
    except Exception as e:
        logger.error(f"❌ Error concatenando conversación | Call ID: {call_event.call.call_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error concatenando conversación: {str(e)}")

# Endpoint de documentación de uso
@app.get("/api-guide")
async def api_guide():
    """
    Guía de uso de los endpoints disponibles
    """
    logger.info("📖 Consulta de guía de API")
    
    return {
        "title": "Call Analysis API - Guía de Uso",
        "version": "1.0.0",
        "endpoints": {
            "webhook": {
                "path": "/webhook",
                "method": "POST",
                "description": "Endpoint para webhooks automáticos - procesa 'call_analyzed' y envía a email por defecto",
                "input": "CallEvent JSON (evento call_analyzed)"
            },
            "auto_email": {
                "path": "/auto-email-report", 
                "method": "POST",
                "description": "Genera PDF y envía automáticamente al email por defecto configurado",
                "input": "CallEvent JSON (evento call_analyzed)"
            },
            "custom_email": {
                "path": "/generate-and-email-report",
                "method": "POST", 
                "description": "Genera PDF y envía al email por defecto - acepta directamente el JSON de call_analyzed",
                "input": "CallEvent JSON (tu JSON exacto)"
            },
            "specific_email": {
                "path": "/email-to-address",
                "method": "POST",
                "description": "Genera PDF y envía a email específico (query parameter)",
                "input": "CallEvent JSON + recipient_email parameter"
            },
            "custom_message": {
                "path": "/send-to-custom-email",
                "method": "POST",
                "description": "Envía con asunto y mensaje personalizado",
                "input": "CallEvent JSON + EmailRequest (email, subject, message)"
            },
            "pdf_only": {
                "path": "/generate-pdf-report",
                "method": "POST",
                "description": "Solo genera PDF para descarga (no envía email)",
                "input": "CallEvent JSON"
            },
            "process_only": {
                "path": "/process-call",
                "method": "POST",
                "description": "Procesa llamada y devuelve análisis (no genera PDF ni email)",
                "input": "CallEvent JSON"
            },
            "concatenate_only": {
                "path": "/concatenate-only",
                "method": "POST",
                "description": "Solo concatena conversación en formato legible",
                "input": "CallEvent JSON"
            }
        },
        "management": {
            "email_config": {
                "get": "/email-config - Ver configuración actual",
                "update_recipient": "/update-default-recipient - Cambiar email por defecto",
                "update_smtp": "/update-email-config - Cambiar configuración SMTP"
            },
            "monitoring": {
                "health": "/health - Health check",
                "logs": "/logs?lines=50 - Ver logs recientes", 
                "stats": "/stats - Estadísticas del sistema"
            }
        },
        "recommended_usage": {
            "webhook_automation": "Usar /webhook para procesamiento automático",
            "manual_reports": "Usar /generate-and-email-report para tu JSON directo",
            "testing": "Usar /process-call para testing sin envío de email"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info("🚀 Iniciando servidor Call Analysis API...")
    logger.info(f"📧 Email configurado: {EMAIL_CONFIG['email_user']}")
    logger.info(f"📧 Destinatario por defecto: {EMAIL_CONFIG.get('default_recipient', 'No configurado')}")
    logger.info("🌐 Servidor disponible en: http://0.0.0.0:8000")
    logger.info("📚 Documentación API en: http://0.0.0.0:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)

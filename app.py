from fastapi import FastAPI, HTTPException , Response
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

app = FastAPI(title="Call Analysis API", version="1.0.0")

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

class CallEventWithEmail(BaseModel):
    event: str
    call: Call
    email_config: EmailRequest

# Configuración de email (puedes usar variables de entorno)
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",  
    "smtp_port": 587,
    "email_user": "aensilesqla@gmail.com", 
    "email_password": "qpjntndxixwxdahn",
    "default_recipient": "aensilesqla@gmail.com",  # Email por defecto NUEVO
}


def send_email_with_pdf(pdf_path: str, recipient_email: str, subject: str, message: str, call_id: str):
    """
    Envía un email con el PDF adjunto
    """
    try:
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["email_user"]
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
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
        
        # Enviar email
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        server.login(EMAIL_CONFIG["email_user"], EMAIL_CONFIG["email_password"])
        
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG["email_user"], recipient_email, text)
        server.quit()
        
        return True
        
    except Exception as e:
        print(f"Error enviando email: {str(e)}")
        return False

app = FastAPI(title="Call Analysis API", version="1.0.0")

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

# Función para concatenar la conversación
def concatenate_conversation(transcript_object: List[TranscriptItem]) -> str:
    """
    Concatena la conversación en un formato legible
    """
    conversation = []
    
    for item in transcript_object:
        role = item.role.capitalize()
        content = item.content
        
        # Formato: "Rol: Contenido"
        conversation.append(f"{role}: {content}")
    
    return "\n".join(conversation)

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
    
    def add_metric_card(self, title, value, status, x_pos, width=60):
        """Crea una tarjeta de métrica moderna"""
        y_start = self.get_y()
        
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
        self.cell(width-30, 8, str(value), 0, 0, 'L')
        
        # Status
        self.set_xy(x_pos + width - 25, y_start + 12)
        self.set_font('Arial', 'B', 8)
        self.cell(20, 6, status, 0, 0, 'R')
        
        return y_start + 30
    
    def add_section_title(self, title, icon=""):
        self.ln(8)
        self.set_font('Arial', 'B', 14)
        self.set_text_color(51, 51, 51)
        full_title = f"{icon} {title}" if icon else title
        self.cell(0, 10, full_title, 0, 1, 'L')
        
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
            
            # Clave en gris
            self.set_xy(x_pos + 2, y_pos + 1)
            self.set_font('Arial', '', 8)
            self.set_text_color(107, 114, 128)
            self.cell(83, 4, key, 0, 0, 'L')
            
            # Valor en negro
            self.set_xy(x_pos + 2, y_pos + 5)
            self.set_font('Arial', 'B', 9)
            self.set_text_color(31, 41, 55)
            
            # Truncar valor si es muy largo
            display_value = str(value)
            if len(display_value) > 25:
                display_value = display_value[:22] + "..."
            
            self.cell(83, 4, display_value, 0, 0, 'L')
        
        self.ln(15)
    
    def add_summary_box(self, text):
        """Crea una caja de resumen moderna"""
        # Fondo de la caja
        self.set_fill_color(249, 250, 251)
        box_height = max(30, len(text) // 80 * 6 + 20)
        self.rect(15, self.get_y(), 180, box_height, 'F')
        
        # Borde izquierdo decorativo
        self.set_fill_color(79, 70, 229)
        self.rect(15, self.get_y(), 4, box_height, 'F')
        
        # Texto del resumen
        self.set_xy(25, self.get_y() + 5)
        self.set_font('Arial', '', 10)
        self.set_text_color(55, 65, 81)
        
        # Dividir texto en líneas
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + word) < 70:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())
        
        for line in lines:
            self.cell(170, 5, line, 0, 1, 'L')
            self.set_x(25)
        
        self.ln(10)
    
    def add_conversation_modern(self, conversation):
        """Formato moderno para la conversación"""
        lines = conversation.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            if line.startswith('User:'):
                # Mensaje del usuario - estilo chat moderno
                self.ln(3)
                message = line[5:].strip()
                
                # Fondo azul claro para usuario
                self.set_fill_color(219, 234, 254)
                msg_height = max(8, len(message) // 60 * 4 + 8)
                self.rect(20, self.get_y(), 160, msg_height, 'F')
                
                # Etiqueta "User"
                self.set_xy(25, self.get_y() + 1)
                self.set_font('Arial', 'B', 8)
                self.set_text_color(30, 64, 175)
                self.cell(0, 3, 'USER', 0, 1, 'L')
                
                # Mensaje
                self.set_x(25)
                self.set_font('Arial', '', 9)
                self.set_text_color(51, 51, 51)
                self.cell(150, 4, message, 0, 1, 'L')
                
            elif line.startswith('Agent:'):
                # Mensaje del agente
                self.ln(3)
                message = line[6:].strip()
                
                # Fondo verde claro para agente
                self.set_fill_color(220, 252, 231)
                msg_height = max(8, len(message) // 60 * 4 + 8)
                self.rect(20, self.get_y(), 160, msg_height, 'F')
                
                # Etiqueta "Agent"
                self.set_xy(25, self.get_y() + 1)
                self.set_font('Arial', 'B', 8)
                self.set_text_color(22, 101, 52)
                self.cell(0, 3, 'AGENT', 0, 1, 'L')
                
                # Mensaje
                self.set_x(25)
                self.set_font('Arial', '', 9)
                self.set_text_color(51, 51, 51)
                self.cell(150, 4, message, 0, 1, 'L')

def generate_pdf_report(call: Call, concatenated_conversation: str, conversation_summary: Dict[str, Any], output_path: str):
    """
    Genera un PDF moderno con métricas visuales
    """
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
    
    # Resumen ejecutivo
    pdf.add_section_title("Summary")
    pdf.add_summary_box(call.call_analysis.call_summary)
    
    # Información de la llamada en grid moderno
    pdf.add_section_title("Call Information")
    
    call_info = [
        ("Call ID", call.call_id[:15] + "..." if len(call.call_id) > 15 else call.call_id),
        ("Status", call.call_status.upper()),
        ("Duration", f"{call.duration_ms / 1000:.1f}s"),
        ("Date", datetime.fromtimestamp(call.start_timestamp / 1000).strftime("%Y-%m-%d")),
        ("Time", datetime.fromtimestamp(call.start_timestamp / 1000).strftime("%H:%M:%S")),
        ("Type", call.call_type.replace("_", " ").title()),
        ("Agent ID", call.agent_id[:12] + "..." if len(call.agent_id) > 12 else call.agent_id),
        ("End Reason", call.disconnection_reason.replace("_", " ").title())
    ]
    
    pdf.add_info_grid(call_info, 2)
    
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
    
    # Nueva página para la transcripción
    pdf.add_page()
    pdf.add_section_title("Full Transcript")
    pdf.add_conversation_modern(concatenated_conversation)
    
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
    
    # Guardar el PDF
    pdf.output(output_path)

def get_conversation_summary(transcript_object: List[TranscriptItem]) -> Dict[str, Any]:
    """
    Genera un resumen de la conversación con estadísticas
    """
    user_messages = [item for item in transcript_object if item.role == "user"]
    agent_messages = [item for item in transcript_object if item.role == "agent"]
    
    return {
        "total_exchanges": len(transcript_object),
        "user_messages": len(user_messages),
        "agent_messages": len(agent_messages),
        "inaudible_speeches": len([item for item in user_messages if "(inaudible speech)" in item.content])
    }

@app.get("/")
async def root():
    return {"message": "Call Analysis API - Envía un POST a /process-call con el JSON de la llamada"}

@app.post("/auto-email-report")
async def auto_email_report(call_event: CallEvent):
    """
    Genera y envía automáticamente a la dirección configurada por defecto
    SOLO procesa eventos 'call_ended' - otros eventos retornan 204
    """
    try:
        # FILTRO: Solo procesar call_ended
        if call_event.event != "call_analyzed":
            return Response(status_code=204)  # No Content - evento ignorado
            
        if not EMAIL_CONFIG.get("default_recipient"):
            raise HTTPException(status_code=400, detail="No default recipient configured. Please set default_recipient in EMAIL_CONFIG")
            
        call = call_event.call
                
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email al destinatario por defecto
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
            except:
                pass
            
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
            return {
                "success": False,
                "message": "Report generated but failed to send email",
                "call_id": call.call_id,
                "pdf_path": pdf_path
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in auto-email: {str(e)}")

@app.post("/email-to-address")
async def email_to_address(call_event: CallEvent, email: EmailStr):
    """
    Genera PDF y envía a un email específico usando query parameter
    SOLO procesa eventos 'call_ended' - otros eventos retornan 204
    """
    try:
        # FILTRO: Solo procesar call_ended
        if call_event.event != "call_ended":
            return Response(status_code=200)  # No Content - evento ignorado
            
        call = call_event.call
        
        # Solo procesar llamadas que realmente terminaron
        if call.call_status != "ended":
            return Response(status_code=204)  # No Content - llamada no terminada
        
        # Concatenar la conversación
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=email,
            subject="Call Analysis Report - Luna Rossa",
            message="Please find attached the complete call analysis report with success metrics, engagement scores, and full conversation transcript.",
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
            "call_id": call.call_id,
            "recipient": email,
            "event_processed": call_event.event
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")

@app.post("/webhook")
async def webhook_endpoint(call_event: CallEvent):
    """
    Endpoint para webhooks automáticos
    SOLO procesa 'call_ended' - retorna 204 para otros eventos
    """
    try:
        # FILTRO PRINCIPAL: Solo procesar call_ended
        if call_event.event != "call_ended":
            return Response(status_code=204)  # No Content - evento ignorado silenciosamente
            
        if not EMAIL_CONFIG.get("default_recipient"):
            # Si no hay destinatario configurado, registrar pero no fallar
            print(f"⚠️ Warning: No default recipient configured for call {call_event.call.call_id}")
            return Response(status_code=204)
            
        call = call_event.call
        
        # Verificar que la llamada realmente terminó
        if call.call_status != "ended":
            return Response(status_code=204)  # No Content - llamada no terminada
        
        # Procesar automáticamente
        concatenated_conversation = concatenate_conversation(call.transcript_object)
        conversation_summary = get_conversation_summary(call.transcript_object)
        
        # Crear archivo temporal para el PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"call_report_{call.call_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # Generar el PDF
        generate_pdf_report(call, concatenated_conversation, conversation_summary, pdf_path)
        
        # Enviar por email
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
        except:
            pass
        
        # Log del resultado (para debugging)
        print(f"📧 Webhook processed: Call {call.call_id} | Email sent: {email_sent} | Recipient: {EMAIL_CONFIG['default_recipient']}")
        
        # Retornar 200 OK para confirmar procesamiento
        return {"success": True, "call_id": call.call_id, "email_sent": email_sent}
        
    except Exception as e:
        # Log del error pero no fallar el webhook
        print(f"❌ Webhook error for call {call_event.call.call_id}: {str(e)}")
        return Response(status_code=204)  # No Content incluso en error

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
async def generate_and_email_report(request: CallEventWithEmail):
    """
    Genera un PDF completo y lo envía por email
    """
    try:
        call = request.call
        email_config = request.email_config
        
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
        
        # Enviar por email
        email_sent = send_email_with_pdf(
            pdf_path=pdf_path,
            recipient_email=email_config.email,
            subject=email_config.subject,
            message=email_config.message,
            call_id=call.call_id
        )
        
        if email_sent:
            # Limpiar archivo temporal
            try:
                os.remove(pdf_path)
            except:
                pass
            
            return {
                "success": True,
                "message": f"Report generated and sent successfully to {email_config.email}",
                "call_id": call.call_id,
                "email_sent": True
            }
        else:
            return {
                "success": False,
                "message": "Report generated but failed to send email",
                "call_id": call.call_id,
                "email_sent": False,
                "pdf_path": pdf_path  # En caso de error, devolver la ruta para descarga manual
            }
        
    except Exception as e:
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
    return {
        "smtp_server": EMAIL_CONFIG["smtp_server"],
        "smtp_port": EMAIL_CONFIG["smtp_port"],
        "sender_email": EMAIL_CONFIG["email_user"],
        "status": "configured" if EMAIL_CONFIG["email_user"] != "tu_email@gmail.com" else "not_configured"
    }

@app.post("/update-email-config")
async def update_email_config(smtp_server: str, smtp_port: int, email_user: str, email_password: str):
    """
    Actualiza la configuración de email
    """
    try:
        EMAIL_CONFIG["smtp_server"] = smtp_server
        EMAIL_CONFIG["smtp_port"] = smtp_port
        EMAIL_CONFIG["email_user"] = email_user
        EMAIL_CONFIG["email_password"] = email_password
        
        return {
            "success": True,
            "message": "Email configuration updated successfully",
            "smtp_server": smtp_server,
            "email_user": email_user
        }
    except Exception as e:
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
    try:
        concatenated = concatenate_conversation(call_event.call.transcript_object)
        return {
            "call_id": call_event.call.call_id,
            "concatenated_conversation": concatenated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error concatenando conversación: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

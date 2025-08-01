
import os
from dotenv import load_dotenv  # Add this import
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr

# Load environment variables BEFORE using them
load_dotenv()

# Load environment variables
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_FROM_NAME="Expense Tracker App",
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)


async def send_reset_email(email_to: EmailStr, username: str):
    reset_link = f"http://localhost:8000/reset-password?email={email_to}"

    message = MessageSchema(
        subject="Password Reset Request - Expense Tracker",
        recipients=[email_to],
        body=f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="margin: 0; font-size: 24px;">🔐 Password Reset Request</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Expense Tracker</p>
            </div>

            <div style="background: #f8fafc; padding: 30px; border-radius: 10px; border: 1px solid #e2e8f0;">
                <p style="font-size: 16px; margin-bottom: 20px;">Hi <strong>{username}</strong>,</p>

                <p style="margin-bottom: 20px;">We received a request to reset your password for your Expense Tracker account.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" 
                       style="display: inline-block; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; 
                              padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; 
                              font-size: 16px;">
                        Reset My Password
                    </a>
                </div>

                <p style="font-size: 14px; color: #64748b;">
                    If you didn't request this, please ignore this email.
                </p>
            </div>

            <div style="text-align: center; margin-top: 30px; color: #64748b; font-size: 12px;">
                <p>© 2024 Expense Tracker. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        subtype="html"
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        print(f"Password reset email sent successfully to {email_to}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise

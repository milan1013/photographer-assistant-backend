import logging

import resend

from app.config import settings

logger = logging.getLogger("fotobir.email")


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email via Resend. Returns True on success."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping email to %s", to_email)
        logger.info("Reset link: %s/reset-password?token=%s", settings.app_url, reset_token)
        return False

    resend.api_key = settings.resend_api_key
    base_url = settings.app_url.rstrip("/")
    reset_url = f"{base_url}/reset-password?token={reset_token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Fotobir - Resetovanje lozinke",
            "html": f"""
            <div style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
                <h2 style="margin-bottom: 16px;">Resetovanje lozinke</h2>
                <p>Primili smo zahtev za resetovanje vase lozinke.</p>
                <p>Kliknite na dugme ispod da postavite novu lozinku:</p>
                <a href="{reset_url}" style="display: inline-block; background: #171717; color: #fafafa; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin: 16px 0;">
                    Resetuj lozinku
                </a>
                <p style="font-size: 14px; color: #737373;">
                    Link istice za {settings.password_reset_expire_minutes} minuta.
                </p>
                <p style="font-size: 14px; color: #737373;">
                    Ako niste vi zahtevali resetovanje, ignorsite ovaj email.
                </p>
                <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 20px 0;" />
                <p style="font-size: 12px; color: #a3a3a3;">Fotobir - Galerije za fotografe i klijente</p>
            </div>
            """,
        })
        logger.info("Password reset email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_verification_email(to_email: str, verify_token: str) -> bool:
    """Send email verification link via Resend."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping verification email to %s", to_email)
        base_url = settings.app_url.rstrip("/")
        logger.info("Verify link: %s/verify-email?token=%s", base_url, verify_token)
        return False

    resend.api_key = settings.resend_api_key
    base_url = settings.app_url.rstrip("/")
    verify_url = f"{base_url}/verify-email?token={verify_token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Fotobir - Potvrdite email adresu",
            "html": f"""
            <div style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
                <h2 style="margin-bottom: 16px;">Dobrodosli u Fotobir!</h2>
                <p>Hvala vam sto ste se registrovali. Potvrdite vasu email adresu klikom na dugme ispod:</p>
                <a href="{verify_url}" style="display: inline-block; background: #171717; color: #fafafa; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin: 16px 0;">
                    Potvrdi email
                </a>
                <p style="font-size: 14px; color: #737373;">
                    Ako niste vi kreirali nalog, ignorsite ovaj email.
                </p>
                <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 20px 0;" />
                <p style="font-size: 12px; color: #a3a3a3;">Fotobir - Galerije za fotografe i klijente</p>
            </div>
            """,
        })
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)
        return False

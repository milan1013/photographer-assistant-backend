import logging

import resend

from app.config import settings

logger = logging.getLogger("fotomil.email")


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email via Resend. Returns True on success."""
    base_url = settings.app_url.rstrip("/")
    reset_url = f"{base_url}/reset-password?token={reset_token}"

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping email to %s", to_email)
        logger.info("Reset link: %s", reset_url)
        return False

    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "FotoMil - Resetovanje lozinke",
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
                <p style="font-size: 12px; color: #a3a3a3;">FotoMil - Galerije za fotografe i klijente</p>
            </div>
            """,
        })
        logger.info("Password reset email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        logger.info("Reset link (fallback): %s", reset_url)
        return False


def send_application_received_to_lab(lab_email: str, lab_name: str) -> bool:
    """Confirm to the applicant that we received their partnership application."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping application receipt to %s", lab_email)
        return False

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [lab_email],
            "subject": "FotoMil - Prijava primljena / Application received",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Prijava za partnerstvo primljena</h2>
                <p>Hvala vam, <strong>{lab_name}</strong>! Primili smo vašu prijavu za partnerstvo sa FotoMil.</p>
                <p>Pregledamo prijavu i kontaktiraćemo vas uskoro.</p>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Application receipt sent to %s", lab_email)
        return True
    except Exception as e:
        logger.error("Failed to send application receipt to %s: %s", lab_email, e)
        return False


def send_application_to_admin(admin_email: str, application_data: dict) -> bool:
    """Notify admin about a new partnership application."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping admin alert to %s", admin_email)
        logger.info("New application: %s", application_data)
        return False

    resend.api_key = settings.resend_api_key
    base_url = settings.app_url.rstrip("/")
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [admin_email],
            "subject": f"FotoMil - Nova prijava laboratorije: {application_data.get('lab_name', '')}",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Nova prijava za partnerstvo</h2>
                <p><strong>Naziv:</strong> {application_data.get("lab_name", "")}</p>
                <p><strong>Email:</strong> {application_data.get("lab_email", "")}</p>
                <p><strong>Telefon:</strong> {application_data.get("lab_phone") or "—"}</p>
                <p><strong>Adresa:</strong> {application_data.get("lab_address") or "—"}</p>
                <p><strong>Veb sajt:</strong> {application_data.get("lab_website") or "—"}</p>
                {f'<p><strong>Poruka:</strong></p><p style="background:#f5f5f5;padding:12px;border-radius:6px;">{application_data.get("message")}</p>' if application_data.get("message") else ""}
                <a href="{base_url}/admin" style="display:inline-block;background:#171717;color:#fafafa;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">
                    Pregledaj u admin panelu
                </a>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Admin alert sent to %s for new application", admin_email)
        return True
    except Exception as e:
        logger.error("Failed to send admin alert to %s: %s", admin_email, e)
        return False


def send_application_approved(lab_email: str, lab_name: str, login_url: str) -> bool:
    """Tell the lab their application was approved.

    A separate Auth0 'set password' email is sent by the approval flow; this email
    is just a friendly welcome pointing them to the lab login page.
    """
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping approval email to %s", lab_email)
        logger.info("Login URL: %s", login_url)
        return False

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [lab_email],
            "subject": "FotoMil - Vaša prijava je odobrena!",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Dobrodošli na FotoMil, {lab_name}!</h2>
                <p>Vaša prijava za partnerstvo je <strong>odobrena</strong>.</p>
                <p>Poslali smo vam zaseban email za podešavanje lozinke. Kada postavite lozinku, prijavite se u portal:</p>
                <a href="{login_url}" style="display:inline-block;background:#171717;color:#fafafa;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">
                    Prijavi se u portal
                </a>
                <p style="font-size:14px;color:#737373;">Ako ne dobijete email za podešavanje lozinke u nekoliko minuta, kontaktirajte nas.</p>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Approval email sent to %s", lab_email)
        return True
    except Exception as e:
        logger.error("Failed to send approval email to %s: %s", lab_email, e)
        return False


def send_application_rejected(lab_email: str, lab_name: str, reason: str | None) -> bool:
    """Tell the lab their application was rejected."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping rejection email to %s", lab_email)
        return False

    resend.api_key = settings.resend_api_key
    try:
        reason_html = f'<p>{reason}</p>' if reason else ''
        resend.Emails.send({
            "from": settings.email_from,
            "to": [lab_email],
            "subject": "FotoMil - Status vaše prijave",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Hvala vam, {lab_name}</h2>
                <p>Nažalost, ne možemo da vam u ovom trenutku odobrimo prijavu za partnerstvo na FotoMil-u.</p>
                {reason_html}
                <p>Cenimo vaše interesovanje i želimo vam puno uspeha.</p>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Rejection email sent to %s", lab_email)
        return True
    except Exception as e:
        logger.error("Failed to send rejection email to %s: %s", lab_email, e)
        return False


def send_lab_magic_link(lab_email: str, token: str) -> bool:
    """Send magic link to lab for logging into the lab portal."""
    base_url = settings.app_url.rstrip("/")
    login_url = f"{base_url}/lab/login?token={token}"

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping magic link to %s", lab_email)
        logger.info("Lab login link: %s", login_url)
        return False

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [lab_email],
            "subject": "FotoMil - Prijava u laboratoriju / Lab login",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Prijava u FotoMil portal za laboratorije</h2>
                <p>Kliknite na dugme ispod da se prijavite u portal za laboratorije:</p>
                <a href="{login_url}" style="display:inline-block;background:#171717;color:#fafafa;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">
                    Prijavi se
                </a>
                <p style="font-size:14px;color:#737373;">Link ističe za {settings.lab_token_expire_hours} sati.</p>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Lab magic link sent to %s", lab_email)
        return True
    except Exception as e:
        logger.error("Failed to send lab magic link to %s: %s", lab_email, e)
        logger.info("Lab login link (fallback): %s", login_url)
        return False


def send_order_notification_to_lab(lab_email: str, order_data: dict) -> bool:
    """Notify lab about a new print order."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping order notification to lab %s", lab_email)
        logger.info("Order data: %s", order_data)
        return False

    resend.api_key = settings.resend_api_key
    items_html = ""
    for item in order_data.get("items", []):
        items_html += f'<tr><td style="padding:6px 8px;border:1px solid #e5e5e5;">{item["filename"]}</td><td style="padding:6px 8px;border:1px solid #e5e5e5;">{item["product"]}</td><td style="padding:6px 8px;border:1px solid #e5e5e5;text-align:center;">{item["quantity"]}</td><td style="padding:6px 8px;border:1px solid #e5e5e5;text-align:right;">{item["unit_price"]}</td><td style="padding:6px 8px;border:1px solid #e5e5e5;text-align:right;">{item["line_total"]}</td></tr>'

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [lab_email],
            "subject": f"FotoMil - Nova narudžbina za štampu ({order_data.get('gallery_name', '')})",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
                <h2>Nova narudžbina za štampu</h2>
                <p><strong>Galerija:</strong> {order_data.get("gallery_name", "")}</p>
                <p><strong>Klijent:</strong> {order_data.get("client_name", "N/A")}</p>
                <p><strong>Email:</strong> {order_data.get("client_email", "N/A")}</p>
                <p><strong>Telefon:</strong> {order_data.get("client_phone", "N/A")}</p>
                {f'<p><strong>Napomena:</strong> {order_data.get("note")}</p>' if order_data.get("note") else ""}
                <table style="width:100%;border-collapse:collapse;margin:16px 0;">
                    <tr style="background:#f5f5f5;"><th style="padding:6px 8px;border:1px solid #e5e5e5;text-align:left;">Fajl</th><th style="padding:6px 8px;border:1px solid #e5e5e5;text-align:left;">Proizvod</th><th style="padding:6px 8px;border:1px solid #e5e5e5;">Kol.</th><th style="padding:6px 8px;border:1px solid #e5e5e5;text-align:right;">Cena</th><th style="padding:6px 8px;border:1px solid #e5e5e5;text-align:right;">Ukupno</th></tr>
                    {items_html}
                </table>
                <p style="font-size:16px;"><strong>Ukupan iznos: {order_data.get("total_price", 0)} {order_data.get("currency", "RSD")}</strong></p>
                {f'<a href="{order_data.get("lab_portal_url")}" style="display:inline-block;background:#171717;color:#fafafa;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">Otvori portal za laboratorije</a>' if order_data.get("lab_portal_url") else ""}
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Order notification sent to lab %s", lab_email)
        return True
    except Exception as e:
        logger.error("Failed to send order notification to lab %s: %s", lab_email, e)
        return False


def send_order_notification_to_photographer(photographer_email: str, order_data: dict) -> bool:
    """Notify photographer about a new print order for their gallery."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping order notification to photographer %s", photographer_email)
        return False

    resend.api_key = settings.resend_api_key
    base_url = settings.app_url.rstrip("/")

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [photographer_email],
            "subject": f"FotoMil - Nova narudžbina za galeriju \"{order_data.get('gallery_name', '')}\"",
            "html": f"""
            <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:20px;">
                <h2>Nova narudžbina za štampu</h2>
                <p>Primili ste novu narudžbinu za galeriju <strong>{order_data.get("gallery_name", "")}</strong>.</p>
                <p><strong>Laboratorija:</strong> {order_data.get("lab_name", "")}</p>
                <p><strong>Klijent:</strong> {order_data.get("client_name", "N/A")}</p>
                <p><strong>Broj stavki:</strong> {order_data.get("item_count", 0)}</p>
                <p><strong>Ukupan iznos:</strong> {order_data.get("total_price", 0)} {order_data.get("currency", "RSD")}</p>
                <a href="{base_url}/gallery/{order_data.get('gallery_id', '')}" style="display:inline-block;background:#171717;color:#fafafa;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">
                    Pogledaj galeriju
                </a>
                <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;" />
                <p style="font-size:12px;color:#a3a3a3;">FotoMil - fotomil.xyz</p>
            </div>
            """,
        })
        logger.info("Order notification sent to photographer %s", photographer_email)
        return True
    except Exception as e:
        logger.error("Failed to send order notification to photographer %s: %s", photographer_email, e)
        return False


def send_verification_email(to_email: str, verify_token: str) -> bool:
    """Send email verification link via Resend."""
    base_url = settings.app_url.rstrip("/")
    verify_url = f"{base_url}/verify-email?token={verify_token}"

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping verification email to %s", to_email)
        logger.info("Verify link: %s", verify_url)
        return False

    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "FotoMil - Potvrdite email adresu",
            "html": f"""
            <div style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
                <h2 style="margin-bottom: 16px;">Dobrodosli u FotoMil!</h2>
                <p>Hvala vam sto ste se registrovali. Potvrdite vasu email adresu klikom na dugme ispod:</p>
                <a href="{verify_url}" style="display: inline-block; background: #171717; color: #fafafa; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin: 16px 0;">
                    Potvrdi email
                </a>
                <p style="font-size: 14px; color: #737373;">
                    Ako niste vi kreirali nalog, ignorsite ovaj email.
                </p>
                <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 20px 0;" />
                <p style="font-size: 12px; color: #a3a3a3;">FotoMil - Galerije za fotografe i klijente</p>
            </div>
            """,
        })
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)
        logger.info("Verify link (fallback): %s", verify_url)
        return False

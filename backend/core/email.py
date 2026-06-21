"""SendGrid magic-link email helper (graceful when keys absent)."""
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def send_magic_link_email(to_email: str, name: str, company_name: str, role: str, magic_link: str) -> Dict[str, Any]:
    """Send a magic-link invite via SendGrid. Returns {sent: bool, reason?: str}."""
    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    sender_email = os.environ.get("SENDER_EMAIL", "")
    if not sendgrid_key or not sender_email:
        return {"sent": False, "reason": "SENDGRID_API_KEY or SENDER_EMAIL not configured"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        html = f"""
        <div style=\"font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0F0F12; color:#F8F9FA; padding:32px; max-width:560px; margin:0 auto;\">
          <div style=\"font-size:11px; letter-spacing:3px; color:#E25822; font-weight:800;\">AIDOU COMMAND</div>
          <h1 style=\"font-size:24px; margin:8px 0 4px;\">You're invited, {name}.</h1>
          <p style=\"color:#A1A1AA; font-size:14px; line-height:20px;\">
            You've been granted access to <strong style=\"color:#F8F9FA;\">{company_name}</strong> as
            <strong style=\"color:#E25822;\">{role.upper()}</strong> on Aidou Command Enterprise Ultimate.
          </p>
          <a href=\"{magic_link}\" style=\"display:inline-block; margin-top:24px; background:#E25822; color:#fff; padding:14px 22px; border-radius:8px; text-decoration:none; font-weight:800; letter-spacing:0.5px;\">Accept invitation →</a>
          <p style=\"color:#6B7280; font-size:11px; margin-top:28px;\">If you weren't expecting this email, just ignore it. The link is single-use and expires in 7 days.</p>
        </div>
        """
        msg = Mail(
            from_email=sender_email,
            to_emails=to_email,
            subject=f"You're invited to Aidou Command — {company_name}",
            html_content=html,
        )
        sg_client = SendGridAPIClient(sendgrid_key)
        resp = sg_client.send(msg)
        return {"sent": 200 <= resp.status_code < 300, "status": resp.status_code}
    except Exception as e:  # pragma: no cover
        logger.warning(f"SendGrid send failed: {e}")
        return {"sent": False, "reason": str(e)}

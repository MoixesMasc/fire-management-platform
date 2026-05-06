"""SNS and SES notification dispatch."""
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared.logging_config import get_logger
from services.notifications.models import FireAlert, NearbyUser

logger = get_logger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.getenv("SNS_FIRE_ALERTS_TOPIC_ARN", "")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "alerts@fire-platform.com")
SES_CONFIGURATION_SET = os.getenv("SES_CONFIGURATION_SET", "")


def _sns_client() -> Any:
    return boto3.client("sns", region_name=AWS_REGION)


def _ses_client() -> Any:
    return boto3.client("ses", region_name=AWS_REGION)


def _build_alert_message(alert: FireAlert, distance_km: float) -> str:
    return (
        f"FIRE ALERT — {alert.severity.upper()} SEVERITY\n\n"
        f"Incident: {alert.title}\n"
        f"Location: {alert.location.latitude:.6f}, {alert.location.longitude:.6f}\n"
        f"Distance from you: {distance_km:.1f} km\n"
        f"Report ID: {alert.report_id}\n"
        f"Validated at: {alert.validated_at}\n\n"
        "Please take immediate precautions and follow local authority instructions."
    )


def _build_email_body(alert: FireAlert, distance_km: float) -> str:
    return f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
  <div style="background-color: #d32f2f; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0;">&#128293; FIRE ALERT</h1>
    <p style="margin: 5px 0;">{alert.severity.upper()} SEVERITY</p>
  </div>
  <div style="padding: 20px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
    <h2>{alert.title}</h2>
    <table style="width: 100%; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px; font-weight: bold;">Location</td>
        <td style="padding: 8px;">{alert.location.latitude:.6f}, {alert.location.longitude:.6f}</td>
      </tr>
      <tr style="background-color: #f5f5f5;">
        <td style="padding: 8px; font-weight: bold;">Distance from you</td>
        <td style="padding: 8px;">{distance_km:.1f} km</td>
      </tr>
      <tr>
        <td style="padding: 8px; font-weight: bold;">Report ID</td>
        <td style="padding: 8px;">{alert.report_id}</td>
      </tr>
      <tr style="background-color: #f5f5f5;">
        <td style="padding: 8px; font-weight: bold;">Validated at</td>
        <td style="padding: 8px;">{alert.validated_at}</td>
      </tr>
    </table>
    <p style="margin-top: 20px; color: #555;">
      Please take immediate precautions and follow local authority instructions.
    </p>
  </div>
</body>
</html>
"""


async def publish_sns_alert(alert: FireAlert) -> list[str]:
    """Publish a fire alert to the SNS topic. Returns list of message IDs."""
    if not SNS_TOPIC_ARN:
        logger.warning("sns_topic_arn_not_configured")
        return []

    client = _sns_client()
    message = _build_alert_message(alert, distance_km=0)
    message_ids: list[str] = []

    try:
        response = client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"FIRE ALERT — {alert.severity.upper()}: {alert.title}",
            Message=message,
            MessageAttributes={
                "severity": {"DataType": "String", "StringValue": alert.severity},
                "report_id": {"DataType": "String", "StringValue": alert.report_id},
            },
        )
        message_ids.append(response["MessageId"])
        logger.info("sns_published", message_id=response["MessageId"], topic=SNS_TOPIC_ARN)
    except ClientError as exc:
        logger.error("sns_publish_failed", error=str(exc), topic=SNS_TOPIC_ARN)

    return message_ids


async def send_ses_email(alert: FireAlert, user: NearbyUser) -> str | None:
    """Send a personalized HTML email via SES. Returns message ID or None on error."""
    client = _ses_client()
    subject = f"FIRE ALERT — {alert.severity.upper()} severity near you ({user.distance_km:.1f}km)"
    html_body = _build_email_body(alert, user.distance_km)
    text_body = _build_alert_message(alert, user.distance_km)

    send_kwargs: dict[str, Any] = {
        "Source": SES_SENDER_EMAIL,
        "Destination": {"ToAddresses": [user.email]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    }
    if SES_CONFIGURATION_SET:
        send_kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

    try:
        response = client.send_email(**send_kwargs)
        message_id = response["MessageId"]
        logger.info("ses_sent", message_id=message_id, email=user.email, report_id=alert.report_id)
        return message_id
    except ClientError as exc:
        logger.error("ses_send_failed", email=user.email, error=str(exc))
        return None

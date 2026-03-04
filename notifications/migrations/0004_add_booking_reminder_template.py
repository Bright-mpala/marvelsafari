from django.db import migrations


BOOKING_REMINDER_TEMPLATE = {
    "name": "Upcoming Stay Reminder",
    "template_type": "booking_reminder",
    "language": "en",
    "subject": "Reminder: {{ property_name }} on {{ check_in_date }}",
    "html_content": (
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"font-family: 'Inter', Arial, sans-serif; background:#f8fafc; padding:32px;\">"
        "  <tr><td align=\"center\">"
        "    <table width=\"640\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#ffffff; border-radius:16px;\">"
        "      <tr>"
        "        <td style=\"padding:32px; color:#0f172a;\">"
        "          <h2 style=\"margin:0 0 12px;\">Your getaway is almost here</h2>"
        "          <p style=\"margin:0 0 16px; color:#475569;\">We will welcome you to <strong>{{ property_name }}</strong> in {{ destination }}.</p>"
        "          <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9; border-radius:12px;\">"
        "            <tr>"
        "              <td style=\"padding:16px;\"><strong>Check-in</strong><br>{{ check_in_date }} · {{ check_in_time }}</td>"
        "              <td style=\"padding:16px;\"><strong>Guests</strong><br>{{ guests }}</td>"
        "            </tr>"
        "            <tr>"
        "              <td style=\"padding:16px;\"><strong>Booking reference</strong><br>{{ booking_reference }}</td>"
        "              <td style=\"padding:16px;\"><strong>Total</strong><br>{{ booking_total }}</td>"
        "            </tr>"
        "          </table>"
        "          <p style=\"margin:24px 0;\">"
        "            <a href=\"{{ manage_booking_url }}\" style=\"background:#0f172a; color:#f8fafc; padding:12px 28px; border-radius:999px; text-decoration:none; font-weight:600;\">Review details</a>"
        "          </p>"
        "          <p style=\"font-size:14px; color:#475569;\">Need transport, chef, or excursions? Concierge is on {{ support_email }}.</p>"
        "        </td>"
        "      </tr>"
        "    </table>"
        "  </td></tr>"
        "</table>"
    ),
    "plain_text_content": (
        "Your stay at {{ property_name }} is around the corner.\n\n"
        "Check-in: {{ check_in_date }} {{ check_in_time }}\n"
        "Guests: {{ guests }}\n"
        "Booking reference: {{ booking_reference }}\n"
        "Total: {{ booking_total }}\n\n"
        "Manage booking: {{ manage_booking_url }}\n"
        "Concierge: {{ support_email }}"
    ),
    "variables": [
        "user_name",
        "property_name",
        "destination",
        "check_in_date",
        "check_in_time",
        "guests",
        "booking_reference",
        "booking_total",
        "manage_booking_url",
        "support_email",
    ],
    "is_active": True,
    "is_default": True,
}


def add_booking_reminder_template(apps, schema_editor):
    EmailTemplate = apps.get_model('notifications', 'EmailTemplate')
    defaults = BOOKING_REMINDER_TEMPLATE.copy()
    defaults.pop('template_type')
    defaults.pop('language')
    EmailTemplate.objects.update_or_create(
        template_type=BOOKING_REMINDER_TEMPLATE['template_type'],
        language=BOOKING_REMINDER_TEMPLATE['language'],
        defaults=defaults,
    )


def remove_booking_reminder_template(apps, schema_editor):
    EmailTemplate = apps.get_model('notifications', 'EmailTemplate')
    EmailTemplate.objects.filter(
        template_type=BOOKING_REMINDER_TEMPLATE['template_type'],
        language=BOOKING_REMINDER_TEMPLATE['language'],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0003_seed_email_templates'),
    ]

    operations = [
        migrations.RunPython(add_booking_reminder_template, remove_booking_reminder_template),
    ]

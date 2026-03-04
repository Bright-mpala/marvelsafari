# Generated manually for AI assistant scaffolding
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('bookings', '0003_alter_booking_options_booking_cancellation_reason_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportThread',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source', models.CharField(choices=[('contact_form', 'Contact Form'), ('email', 'Inbound Email'), ('booking', 'Booking Flow'), ('deal', 'Deal Lead'), ('chat', 'Live Chat')], default='contact_form', max_length=30)),
                ('channel', models.CharField(choices=[('email', 'Email'), ('in_app', 'In-App'), ('sms', 'SMS'), ('web', 'Web Form')], default='email', max_length=20)),
                ('thread_key', models.CharField(blank=True, help_text='External thread identifier or message-id', max_length=255)),
                ('customer_name', models.CharField(blank=True, max_length=255)),
                ('customer_email', models.EmailField(blank=True, max_length=254)),
                ('subject', models.CharField(blank=True, max_length=255)),
                ('latest_customer_message', models.TextField(blank=True)),
                ('raw_messages', models.JSONField(blank=True, default=list)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('intent_label', models.CharField(blank=True, max_length=50)),
                ('sentiment_score', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal', max_length=20)),
                ('status', models.CharField(choices=[('new', 'New'), ('triaged', 'Triaged'), ('waiting', 'Waiting On Customer'), ('in_progress', 'In Progress'), ('auto_replied', 'Auto Replied'), ('closed', 'Closed')], default='new', max_length=20)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('ai_summary', models.TextField(blank=True)),
                ('ai_suggested_reply', models.TextField(blank=True)),
                ('ai_recommended_actions', models.JSONField(blank=True, default=list)),
                ('deal_recommendations', models.JSONField(blank=True, default=list)),
                ('booking_insights', models.JSONField(blank=True, default=dict)),
                ('last_ai_provider', models.CharField(blank=True, max_length=50)),
                ('last_ai_latency_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('last_ai_run_at', models.DateTimeField(blank=True, null=True)),
                ('auto_reply_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_support_threads', to=settings.AUTH_USER_MODEL)),
                ('related_booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_threads', to='bookings.booking')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AIAssistantInsight',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('object_id', models.CharField(blank=True, max_length=64)),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField(blank=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('insight_type', models.CharField(choices=[('support_triage', 'Support Triage'), ('booking_summary', 'Booking Summary'), ('deal_recommendation', 'Deal Recommendation'), ('automation', 'Automation')], max_length=40)),
                ('provider', models.CharField(blank=True, max_length=50)),
                ('tokens_consumed', models.PositiveIntegerField(blank=True, null=True)),
                ('latency_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_assistant_insights', to=settings.AUTH_USER_MODEL)),
                ('thread', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='insights', to='ai_assistant.supportthread')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='supportthread',
            index=models.Index(fields=['status', 'priority'], name='ai_assista_status_0d14d9_idx'),
        ),
        migrations.AddIndex(
            model_name='supportthread',
            index=models.Index(fields=['source', 'channel'], name='ai_assista_source_183c7d_idx'),
        ),
        migrations.AddIndex(
            model_name='supportthread',
            index=models.Index(fields=['customer_email'], name='ai_assista_customer_a8b82d_idx'),
        ),
        migrations.AddIndex(
            model_name='aiassistantinsight',
            index=models.Index(fields=['insight_type'], name='ai_assista_insight_39927a_idx'),
        ),
        migrations.AddIndex(
            model_name='aiassistantinsight',
            index=models.Index(fields=['created_at'], name='ai_assista_created_77a448_idx'),
        ),
    ]

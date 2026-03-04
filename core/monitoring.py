"""Monitoring and metrics for enterprise observability"""

import logging
from prometheus_client import Counter, Histogram, Gauge
import time

logger = logging.getLogger(__name__)

# Metrics containers
_metrics_initialized = False


def setup_metrics():
    """Initialize Prometheus metrics"""
    global _metrics_initialized
    if _metrics_initialized:
        return
    
    try:
        # Request metrics
        global http_requests_total, http_request_duration_seconds, http_requests_in_progress
        
        http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status']
        )
        
        http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
        )
        
        http_requests_in_progress = Gauge(
            'http_requests_in_progress',
            'HTTP requests in progress'
        )
        
        # Database metrics
        global db_query_duration_seconds, db_connections_active
        
        db_query_duration_seconds = Histogram(
            'db_query_duration_seconds',
            'Database query duration in seconds',
            ['operation']
        )
        
        db_connections_active = Gauge(
            'db_connections_active',
            'Active database connections'
        )
        
        # Business metrics
        global bookings_created_total, bookings_cancelled_total, bookings_completed_total
        
        bookings_created_total = Counter(
            'bookings_created_total',
            'Total bookings created'
        )
        
        bookings_cancelled_total = Counter(
            'bookings_cancelled_total',
            'Total bookings cancelled'
        )
        
        bookings_completed_total = Counter(
            'bookings_completed_total',
            'Total bookings completed'
        )
        
        # Celery metrics
        global celery_tasks_total, celery_task_duration_seconds
        
        celery_tasks_total = Counter(
            'celery_tasks_total',
            'Total Celery tasks executed',
            ['task_name', 'status']
        )
        
        celery_task_duration_seconds = Histogram(
            'celery_task_duration_seconds',
            'Celery task duration in seconds',
            ['task_name']
        )
        
        _metrics_initialized = True
        logger.info("Prometheus metrics initialized")
        
    except Exception as e:
        logger.warning(f"Failed to initialize metrics: {e}")


class MetricsRecorder:
    """Context manager for recording metrics"""
    
    def __init__(self, metric_name, labels=None):
        self.metric_name = metric_name
        self.labels = labels or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        # Record to appropriate metric
        if self.metric_name == 'database_query':
            operation = self.labels.get('operation', 'unknown')
            db_query_duration_seconds.labels(operation=operation).observe(duration)
        
        elif self.metric_name == 'celery_task':
            task_name = self.labels.get('task_name', 'unknown')
            celery_task_duration_seconds.labels(task_name=task_name).observe(duration)


def record_booking_created():
    """Record booking creation metric"""
    if _metrics_initialized:
        bookings_created_total.inc()


def record_booking_cancelled():
    """Record booking cancellation metric"""
    if _metrics_initialized:
        bookings_cancelled_total.inc()


def record_booking_completed():
    """Record booking completion metric"""
    if _metrics_initialized:
        bookings_completed_total.inc()

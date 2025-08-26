"""
QuantTime Celery Application

Celery application for distributed task processing across the computing cluster.
"""

import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from celery import Celery
from server.core.job_manager import JobManager

# Initialize Celery app
app = Celery('quanttime_tasks')

# Configure Celery for distributed server processing
app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours default timeout for heavy jobs
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,  # Lower for memory management
    
    # Server-based task routing (all servers can handle all tasks)
    task_routes={
        # Route to specific servers based on queue
        'server.core.job_manager.execute_job_task': {
            'queue': 'default'  # Will be overridden by apply_async
        }
    },
    
    # Queue configuration for each server
    task_default_queue='server_laptop',
    task_create_missing_queues=True,
    
    # Define all server queues
    task_routes={
        # Default routing - jobs will specify queue explicitly
    },
    
    # Worker configuration
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Performance settings
    task_compression='gzip',
    result_compression='gzip',
    task_ignore_result=False,
    result_expires=86400,  # 24 hours
    
    # Reliability settings  
    task_acks_late=True,
    worker_disable_rate_limits=True,
    task_reject_on_worker_lost=True,
)

if __name__ == '__main__':
    app.start()

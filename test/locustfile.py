import time

from locust import HttpUser, task, between
import uuid
import random
from datetime import datetime, timedelta, UTC
import copy
import logging

logger = logging.getLogger(__name__)

test_json_template = {
    "product_id": None,
    "event_datetime": None,
    "client_id": None,
    "event_name": "product_viewed",
    "inserted_dt": None,
    "sid": None,
    "r": "ref_001",
    "additional_fields": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "location": "Moscow",
        "device": "desktop",
        "ab_test_group": "B"
    }
}


class TestUser(HttpUser):
    # wait_time = between(0.001, 0.003)  # Слишком большое время ожидания
    wait_time = lambda self: 0  # Без паузы между запросами

    def generate_event_json(self):
        now = datetime.now(UTC)
        event_time = now - timedelta(seconds=random.randint(0, 300))

        event = copy.deepcopy(test_json_template)
        event["product_id"] = str(uuid.uuid4())
        event["event_datetime"] = event_time.isoformat()
        event["inserted_dt"] = now.isoformat()
        event["client_id"] = random.randint(1, 100000)
        event["sid"] = str(uuid.uuid4())
        return event

    @task
    def send_event(self):
        payload = self.generate_event_json()
        start_time = time.time()  # Засекаем время начала запроса
        try:
            with self.client.post("/event", json=payload, catch_response=True) as response:
                total_time = (time.time() - start_time) * 1000  # Время в миллисекундах
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 400:
                    if "not unique" in response.text or "Missing product_id" in response.text:
                        response.success()
                    else:
                        response.failure("Unexpected 400: %s" % response.text)
                else:
                    response.failure("%s: %s" % (response.status_code, response.text))
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logger.error("Request to /event failed with exception: %s. Time taken: %.2fms" % (str(e), total_time))

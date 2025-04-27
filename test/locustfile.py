from locust import HttpUser, task
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
    # wait_time = between(0.001, 0.003)  # Время ожидания
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
        try:
            with self.client.post("/event", json=payload, catch_response=True) as response:
                elapsed_ms = response.elapsed.total_seconds() * 1000  # Время в миллисекундах
                if response.status_code == 200:
                    response.success()
                    logger.info("Request to /event succeeded. Time taken: %.2f ms", elapsed_ms)
                elif response.status_code == 400:
                    if "not unique" in response.text or "Missing product_id" in response.text:
                        response.success()
                        logger.info("Request to /event expected 400. Time taken: %.2f ms", elapsed_ms)
                    else:
                        response.failure("Unexpected 400: %s" % response.text)
                else:
                    response.failure("%s: %s" % (response.status_code, response.text))
        except Exception as e:
            logger.error("Request to /event failed with exception: %s", str(e))

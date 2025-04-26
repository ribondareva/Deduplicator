from locust import HttpUser, task, between, events
import time
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
    wait_time = between(0.1, 0.5)

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
        # logger.info("Locust тест запускается после успешного health-check")
        payload = self.generate_event_json()
        start_time = time.time()

        try:
            with self.client.post("/event", json=payload, catch_response=True) as response:
                total_time = int((time.time() - start_time) * 1000)
                logger.info("Status: %s | Time: %ss" % (response.status_code, response.elapsed.total_seconds()))

                if response.status_code != 200:
                    response.failure("%s: %s" % (response.status_code, response.text))
                    events.request.fire(
                        request_type="POST",
                        name="POST /event",
                        response_time=total_time,
                        response_length=len(response.content),
                        exception="%s: %s" % (response.status_code, response.text)
                    )
                    return

                events.request.fire(
                    request_type="POST",
                    name="POST /event",
                    response_time=total_time,
                    response_length=len(response.content),
                    exception=None
                )
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            logger.error("Request failed: %s" % str(e))
            events.request.fire(
                request_type="POST",
                name="POST /event",
                response_time=total_time,
                response_length=0,
                exception=str(e)
            )

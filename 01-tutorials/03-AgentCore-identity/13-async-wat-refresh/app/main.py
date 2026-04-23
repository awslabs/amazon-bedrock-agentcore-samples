"""
Threaded async agent — WAT refresh test.
Wait 6 min, then 3 credential provider calls.
No model needed — just testing the decorator/helper WAT refresh mechanism.
"""

import time
import logging
from datetime import datetime, timezone

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agentcore_thread_utils import with_wat_refresh, ThreadTaskManager, set_task_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SCAFFOLDING
app = BedrockAgentCoreApp()
manager = ThreadTaskManager(app)


# DEVELOPER CODE — credential provider call
@with_wat_refresh(
    provider_name="cognito-m2m-provider",
    scopes=["https://agent-api.example.com/invoke"],
    auth_flow="M2M",
)
def call_my_api(*, access_token: str) -> dict:
    return {"success": True, "timestamp": datetime.now(timezone.utc).isoformat()}


# DEVELOPER CODE — business logic
def my_long_running_job(*, task_id: int):
    set_task_context(manager, task_id)
    results = []

    logger.info(f"[Task {task_id}] Waiting 6 minutes...")
    for m in range(1, 7):
        time.sleep(60)
        logger.info(f"[Task {task_id}] {m}/6 min")

    for i in range(1, 4):
        logger.info(f"[Task {task_id}] Test {i}/3...")
        r = call_my_api(access_token="")
        results.append(r)
        logger.info(f"[Task {task_id}] Test {i} done: {r}")
        if i < 3:
            logger.info(f"[Task {task_id}] Waiting 6 minutes before next test...")
            for m in range(1, 7):
                time.sleep(60)
                logger.info(f"[Task {task_id}] {m}/6 min")

    return {"status": "completed", "tests": results}


# SCAFFOLDING
manager.register_task(my_long_running_job)


@app.entrypoint
def handler(payload, context):
    return manager.handle(payload, context)


if __name__ == "__main__":
    app.run()

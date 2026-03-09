"""
Queue Trigger Simulator for Azure Functions.

Provides classes for simulating Azure Functions queue triggers
with in-memory queue storage and message processing.
"""

import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


@dataclass
class QueueMessage:
    """Represents a message in an Azure Storage Queue."""

    body: Any
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    insertion_time: datetime = field(default_factory=datetime.utcnow)
    expiration_time: Optional[datetime] = None
    dequeue_count: int = 0
    pop_receipt: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if self.expiration_time is None:
            self.expiration_time = self.insertion_time + timedelta(days=7)

    def get_body(self) -> str:
        """Return the message body as a string."""
        if isinstance(self.body, (dict, list)):
            return json.dumps(self.body)
        return str(self.body)

    def get_json(self) -> Any:
        """Parse and return the message body as JSON."""
        if isinstance(self.body, (dict, list)):
            return self.body
        try:
            return json.loads(str(self.body))
        except (json.JSONDecodeError, ValueError):
            return None

    def to_dict(self) -> Dict:
        """Convert the message to a dictionary representation."""
        return {
            "id": self.id,
            "body": self.body,
            "insertion_time": self.insertion_time.isoformat(),
            "expiration_time": self.expiration_time.isoformat() if self.expiration_time else None,
            "dequeue_count": self.dequeue_count,
        }


class InMemoryQueue:
    """In-memory queue storage for simulation purposes."""

    def __init__(self, name: str, max_size: int = 10000):
        self.name = name
        self.max_size = max_size
        self._queue: deque = deque(maxlen=max_size)
        self._dead_letter: List[QueueMessage] = []

    def enqueue(self, message: Any) -> QueueMessage:
        """Add a message to the queue."""
        if isinstance(message, QueueMessage):
            msg = message
        else:
            msg = QueueMessage(body=message)
        self._queue.append(msg)
        return msg

    def dequeue(self) -> Optional[QueueMessage]:
        """Remove and return the next message from the queue."""
        if self._queue:
            msg = self._queue.popleft()
            msg.dequeue_count += 1
            return msg
        return None

    def peek(self) -> Optional[QueueMessage]:
        """View the next message without removing it."""
        if self._queue:
            return self._queue[0]
        return None

    def move_to_dead_letter(self, message: QueueMessage) -> None:
        """Move a message to the dead letter queue."""
        self._dead_letter.append(message)

    @property
    def length(self) -> int:
        """Return the number of messages in the queue."""
        return len(self._queue)

    @property
    def dead_letter_count(self) -> int:
        """Return the number of dead letter messages."""
        return len(self._dead_letter)


class QueueTrigger:
    """
    Simulates an Azure Functions queue trigger.

    Processes messages from an in-memory queue simulation.
    """

    MAX_DEQUEUE_COUNT = 5

    def __init__(
        self,
        queue_name: str,
        connection: str = "AzureWebJobsStorage",
        batch_size: int = 1,
    ):
        self.queue_name = queue_name
        self.connection = connection
        self.batch_size = batch_size
        self._handler: Optional[Callable] = None
        self._queue = InMemoryQueue(queue_name)
        self._processing_log: List[Dict] = []

    def __call__(self, func: Callable) -> Callable:
        """Register a function as the handler for this trigger."""
        self._handler = func
        func._trigger = self
        return func

    def send_message(self, body: Any) -> QueueMessage:
        """Add a message to the queue for processing."""
        return self._queue.enqueue(body)

    def invoke(self, message: Optional[QueueMessage] = None) -> Dict:
        """
        Invoke the queue trigger handler with a message.

        If no message is provided, dequeues from the internal queue.
        """
        if not self._handler:
            return {"status": "error", "message": "No handler registered"}

        msg = message or self._queue.dequeue()
        if msg is None:
            return {"status": "no_message", "message": "Queue is empty"}

        start_time = datetime.utcnow()

        try:
            result = self._handler(msg)
            record = {
                "function": self._handler.__name__,
                "queue": self.queue_name,
                "message_id": msg.id,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "success",
                "result": result,
                "dequeue_count": msg.dequeue_count,
            }
        except Exception as exc:
            if msg.dequeue_count >= self.MAX_DEQUEUE_COUNT:
                self._queue.move_to_dead_letter(msg)
                record = {
                    "function": self._handler.__name__,
                    "queue": self.queue_name,
                    "message_id": msg.id,
                    "started_at": start_time.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "status": "dead_lettered",
                    "error": str(exc),
                    "dequeue_count": msg.dequeue_count,
                }
            else:
                self._queue.enqueue(msg)
                record = {
                    "function": self._handler.__name__,
                    "queue": self.queue_name,
                    "message_id": msg.id,
                    "started_at": start_time.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "status": "retry",
                    "error": str(exc),
                    "dequeue_count": msg.dequeue_count,
                }

        self._processing_log.append(record)
        return record

    def process_batch(self) -> List[Dict]:
        """Process up to batch_size messages from the queue."""
        results = []
        for _ in range(min(self.batch_size, self._queue.length)):
            result = self.invoke()
            results.append(result)
        return results

    def get_queue_info(self) -> Dict:
        """Return information about the queue state."""
        return {
            "name": self.queue_name,
            "length": self._queue.length,
            "dead_letter_count": self._queue.dead_letter_count,
            "total_processed": len(self._processing_log),
        }

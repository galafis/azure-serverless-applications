"""
Blob Trigger Simulator for Azure Functions.

Provides classes for simulating Azure Functions blob triggers
with in-memory blob storage operations.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BlobProperties:
    """Represents the properties of an Azure Blob."""

    name: str
    container: str
    content: bytes = b""
    content_type: str = "application/octet-stream"
    blob_type: str = "BlockBlob"
    size: int = 0
    etag: str = ""
    last_modified: datetime = field(default_factory=datetime.utcnow)
    created_on: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.size:
            self.size = len(self.content)
        if not self.etag:
            self.etag = hashlib.md5(self.content).hexdigest()

    @property
    def uri(self) -> str:
        """Return a simulated blob URI."""
        return f"https://storage.local/{self.container}/{self.name}"

    def to_dict(self) -> Dict:
        """Convert blob properties to a dictionary."""
        return {
            "name": self.name,
            "container": self.container,
            "content_type": self.content_type,
            "blob_type": self.blob_type,
            "size": self.size,
            "etag": self.etag,
            "last_modified": self.last_modified.isoformat(),
            "created_on": self.created_on.isoformat(),
            "metadata": self.metadata,
            "uri": self.uri,
        }


class InMemoryBlobStorage:
    """In-memory blob storage simulation."""

    def __init__(self):
        self._containers: Dict[str, Dict[str, BlobProperties]] = {}

    def create_container(self, name: str) -> None:
        """Create a new blob container."""
        if name not in self._containers:
            self._containers[name] = {}

    def upload_blob(
        self,
        container: str,
        name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> BlobProperties:
        """Upload a blob to a container."""
        self.create_container(container)
        blob = BlobProperties(
            name=name,
            container=container,
            content=content,
            content_type=content_type,
            metadata=metadata or {},
        )
        self._containers[container][name] = blob
        return blob

    def get_blob(self, container: str, name: str) -> Optional[BlobProperties]:
        """Retrieve a blob from a container."""
        return self._containers.get(container, {}).get(name)

    def delete_blob(self, container: str, name: str) -> bool:
        """Delete a blob from a container."""
        if container in self._containers and name in self._containers[container]:
            del self._containers[container][name]
            return True
        return False

    def list_blobs(self, container: str) -> List[BlobProperties]:
        """List all blobs in a container."""
        return list(self._containers.get(container, {}).values())


class BlobTrigger:
    """
    Simulates an Azure Functions blob trigger.

    Fires when a blob is created or updated in the monitored container.
    """

    def __init__(
        self,
        path: str,
        connection: str = "AzureWebJobsStorage",
    ):
        parts = path.split("/", 1)
        self.container = parts[0]
        self.blob_pattern = parts[1] if len(parts) > 1 else "{name}"
        self.connection = connection
        self._handler: Optional[Callable] = None
        self._storage = InMemoryBlobStorage()
        self._storage.create_container(self.container)
        self._event_log: List[Dict] = []

    def __call__(self, func: Callable) -> Callable:
        """Register a function as the handler for this trigger."""
        self._handler = func
        func._trigger = self
        return func

    def upload_and_trigger(
        self,
        blob_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Upload a blob and trigger the function.

        Simulates the Azure blob trigger behavior where uploading
        or updating a blob fires the function.
        """
        blob = self._storage.upload_blob(
            container=self.container,
            name=blob_name,
            content=content,
            content_type=content_type,
            metadata=metadata,
        )
        return self.invoke(blob)

    def invoke(self, blob: BlobProperties) -> Dict:
        """Invoke the blob trigger handler with the given blob."""
        if not self._handler:
            return {"status": "error", "message": "No handler registered"}

        start_time = datetime.utcnow()

        try:
            result = self._handler(blob)
            record = {
                "function": self._handler.__name__,
                "container": self.container,
                "blob_name": blob.name,
                "blob_size": blob.size,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "success",
                "result": result,
            }
        except Exception as exc:
            record = {
                "function": self._handler.__name__,
                "container": self.container,
                "blob_name": blob.name,
                "blob_size": blob.size,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(exc),
            }

        self._event_log.append(record)
        return record

    def get_storage(self) -> InMemoryBlobStorage:
        """Return the internal blob storage for testing."""
        return self._storage

    def get_event_log(self) -> List[Dict]:
        """Return the event history."""
        return list(self._event_log)

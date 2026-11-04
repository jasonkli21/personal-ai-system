"""Bounded canonical memory-domain episode projection; atomic namespace updates."""

from contextlib import contextmanager
from copy import deepcopy
from threading import RLock


def empty_bucket():
    return {
        "schema_version": "episode-bucket-v1",
        "records": {},
        "states": {},
        "receipts": {},
        "events": {},
    }


class InMemoryEpisodeRepository:
    def __init__(self):
        self.buckets = {}
        self.lock = RLock()

    @contextmanager
    def locked(self, owner_id, namespace):
        with self.lock:
            key = (owner_id, namespace)
            bucket = deepcopy(self.buckets.get(key, empty_bucket()))
            original = deepcopy(bucket)
            yield bucket
            if bucket == original:
                return
            if key not in self.buckets and len(self.buckets) >= 128:
                raise ValueError("episode_namespace_capacity")
            self.buckets[key] = bucket

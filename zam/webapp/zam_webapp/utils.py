import os
from contextlib import contextmanager
from typing import Dict, Iterator


@contextmanager
def environ(env: Dict[str, str]) -> Iterator[None]:
    """Temporarily set environment variables inside the context manager and
    fully restore previous environment afterwards

    Based on: https://gist.github.com/igniteflow/7267431
    """
    original_env = {key: os.getenv(key) for key in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for key, value in original_env.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value

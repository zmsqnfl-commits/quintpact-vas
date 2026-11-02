"""A project-specific, append-only witness for remounts of packaged starters."""
import os
import re
import uuid

from vas_portable_progress import _directory

ANCHOR = re.compile(r"[0-9a-f]{32}")
NAMES = ("vas-state", "target-identity")


def project_anchor(root, expected=None):
    """Only explicit bindings create an anchor. Reads never repair or adopt another."""
    with _directory(root, expected is None, NAMES) as directory:
        if directory is None:
            return None
        name = expected and expected["id"]
        flags = os.O_RDONLY
        if expected is None:
            # A zero-byte, random name is published in one exclusive create. Concurrent
            # first binds can each safely keep their own witness without a lock or rename.
            with os.scandir(directory.fd if directory.fd is not None else directory.path) as entries:
                for count, entry in enumerate(entries, 1):
                    if count > 64 or not ANCHOR.fullmatch(entry.name):
                        raise ValueError("target_identity_invalid")
                    if name is None or entry.name < name:
                        name = entry.name
            if name is None:
                name = uuid.uuid4().hex
                flags |= os.O_CREAT | os.O_EXCL
        try:
            with directory.file(name, flags) as fd:
                info = os.fstat(fd)
                if info.st_size or not info.st_ino:
                    raise ValueError("target_identity_invalid")
                return {"id": name, "inode": info.st_ino}
        except FileNotFoundError:
            if expected is None:
                raise
            return None

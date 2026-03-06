import difflib
import shutil
import time
from pathlib import Path


class TimeMachine:
    def __init__(self, filepath: Path):
        if not filepath.exists():
            raise FileNotFoundError(f"Path {filepath} does not exist")
        if not filepath.is_file():
            raise ValueError(f"Path {filepath} is not a file")

        self.filepath = filepath.resolve()
        self.filename = self.filepath.name
        self.snapshots_dir = self.filepath.parent / ".time_machine" / self.filename

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.commit()

    def _new_snapshot(self) -> Path:
        def p():
            return self.snapshots_dir / (time.strftime("%Y%m%d.%H%M%S") + "." + self.filename)

        new_snapshot = p()
        while new_snapshot.exists():
            time.sleep(1)
            new_snapshot = p()
        return new_snapshot

    @property
    def snapshots(self) -> list[Path]:
        return sorted(self.snapshots_dir.glob(f"*.{self.filename}"))

    @property
    def last_snapshot(self) -> Path | None:
        snapshots = self.snapshots
        if len(snapshots) == 0:
            return None
        return snapshots[-1]

    def is_committed(self) -> bool:
        last_snapshot = self.last_snapshot
        if last_snapshot is None:
            return False
        return self.filepath.read_bytes() == last_snapshot.read_bytes()

    def commit(self):
        if not self.is_committed():
            shutil.copy(self.filepath, self._new_snapshot())

    def diff(self) -> str:
        last_snapshot = self.last_snapshot

        if last_snapshot is None:
            last_snapshot = self.filepath

        return "\n".join(
            difflib.unified_diff(
                last_snapshot.read_text().splitlines(),
                self.filepath.read_text().splitlines(),
                fromfile="Old",
                tofile="New",
                lineterm="",
            )
        )

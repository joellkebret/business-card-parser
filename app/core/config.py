from dataclasses import dataclass, field
import os
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[2]
LIBRARY_NAME = 'vcparser.dll' if os.name == 'nt' else ('libvcparser.dylib' if platform.system() == 'Darwin' else 'libvcparser.so')


@dataclass(frozen=True)
class Settings:
    library_path: Path = field(default_factory=lambda: Path(os.getenv('VCARD_LIBRARY_PATH', str(ROOT / 'build' / LIBRARY_NAME))))
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', 'sqlite:///data/cards.db'))
    max_upload_bytes: int = field(default_factory=lambda: int(os.getenv('MAX_UPLOAD_BYTES', '1048576')))

    def __post_init__(self):
        if self.max_upload_bytes < 1:
            raise ValueError('MAX_UPLOAD_BYTES must be positive')

from abc import ABC, abstractmethod


class SecretReader(ABC):
    @abstractmethod
    def read_secret(self, name: str) -> str:
        """Get secret value by name."""
        pass

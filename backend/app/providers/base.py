from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    async def generate_with_image(self, prompt: str, image_path: str, system: str = "") -> str:
        """Generate text from a prompt + image (for VLM)."""
        ...

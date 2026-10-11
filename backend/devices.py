from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from .models import OutputDef

Event = dict[str, Any]
Emitter = Callable[[Event], Awaitable[None]]


class Device(ABC):
    def __init__(self, output: OutputDef):
        self.output = output

    @abstractmethod
    async def apply(self, valor: Any) -> None:
        ...


class VirtualDevice(Device):
    def __init__(self, output: OutputDef, emit: Emitter):
        super().__init__(output)
        self.emit = emit

    async def apply(self, valor: Any) -> None:
        await self.emit(
            {
                "type": "command",
                "output_id": self.output.id,
                "output_name": self.output.name,
                "valor": valor,
            }
        )

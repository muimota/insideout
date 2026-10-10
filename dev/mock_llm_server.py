import json
import re

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

DECISIONES = {"Prudente": "ROJO", "Ahorrador": "OFF"}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    system = body["messages"][0]["content"]
    agent_name = re.search(r'Eres "([^"]+)"', system).group(1)
    output_id = re.search(r'"([0-9a-f]{8})" \(', system).group(1)
    valor = DECISIONES.get(agent_name, "AMBAR")
    args = json.dumps(
        {
            "output_id": output_id,
            "valor": valor,
            "justificacion": f"como {agent_name}, prefiero {valor}",
        }
    )

    def chunk(delta):
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "model": "mock-model",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }

    async def gen():
        for piece in ("Argumento: ", "mi postura es ", f"proponer {valor}."):
            yield f"data: {json.dumps(chunk({'content': piece}))}\n\n"
        yield (
            "data: "
            + json.dumps(
                chunk(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "propose_output", "arguments": ""},
                            }
                        ]
                    }
                )
            )
            + "\n\n"
        )
        half = len(args) // 2
        for part in (args[:half], args[half:]):
            yield (
                "data: "
                + json.dumps(
                    chunk(
                        {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": part},
                                }
                            ]
                        }
                    )
                )
                + "\n\n"
            )
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

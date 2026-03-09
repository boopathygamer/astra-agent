import asyncio
import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

logger = logging.getLogger(__name__)
router = APIRouter()

class NeuralUplinkManager:
    """
    High-Throughput Zero-Latency Streaming Protocol.
    Replaces standard REST endpoints with a bidirectional stream for
    character-by-character AST and token rendering in the frontend studio.
    Using WebSockets as a proxy for gRPC/WebRTC to maintain vast browser compat.
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"🔗 [Neural Uplink] Established zero-latency stream with client: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"🔌 [Neural Uplink] Stream severed for client: {client_id}")

    async def broadcast_token(self, client_id: str, token: str, stream_id: str = "main"):
        """Streams a single string/character/token directly into the frontend UI instantly."""
        if client_id in self.active_connections:
            payload = {
                "type": "token_stream",
                "stream_id": stream_id,
                "token": token
            }
            # For ultra-performance, in production this would be MessagePack binary.
            # We use JSON text payload here for the MVP architecture.
            try:
                await self.active_connections[client_id].send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"[Neural Uplink] Token delivery failed: {e}")

    async def broadcast_ast_patch(self, client_id: str, file_path: str, diff_hunk: str):
        """Streams live code mutation logic (AST diffs) as the Swarm generates it."""
        if client_id in self.active_connections:
            payload = {
                "type": "ast_patch",
                "file": file_path,
                "diff": diff_hunk
            }
            await self.active_connections[client_id].send_text(json.dumps(payload))

uplink_manager = NeuralUplinkManager()

@router.websocket("/ws/neural_uplink/{client_id}")
async def neural_uplink_endpoint(websocket: WebSocket, client_id: str):
    """
    The actual FastAPI WebSocket mount point for the Frontend Web Studio.
    Example JS client connection:
    const ws = new WebSocket('ws://localhost:8000/ws/neural_uplink/studio_1');
    """
    await uplink_manager.connect(client_id, websocket)
    try:
        while True:
            # Maintain duplex open connection. Await commands from the UI.
            data = await websocket.receive_text()
            
            # The client might send cursor movements, keystrokes, or active files over this socket.
            # We could pipe this directly into the PreCognitiveCache!
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        uplink_manager.disconnect(client_id)

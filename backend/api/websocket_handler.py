"""
WebSocket Handler — Real-Time Bi-directional Chat API
═════════════════════════════════════════════════════
Provides a WebSocket endpoint for real-time chat with the AI agent.
Supports persistent connections, streaming responses, and session management.

Usage:
    ws://localhost:8000/ws/chat
    
    Send: {"type": "message", "content": "Hello", "session_id": "optional"}
    Recv: {"type": "token", "content": "Hi", "index": 1}
    Recv: {"type": "done", "tokens": 42, "duration_ms": 1234}
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id} (total: {len(self.active)})")
    
    def disconnect(self, client_id: str):
        self.active.pop(client_id, None)
        logger.info(f"WebSocket disconnected: {client_id} (total: {len(self.active)})")
    
    async def send_json(self, client_id: str, data: dict):
        ws = self.active.get(client_id)
        if ws:
            await ws.send_json(data)
    
    async def broadcast(self, data: dict):
        for ws in self.active.values():
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


async def _process_message(content: str, session_id: str) -> str:
    """Process a message through the agent controller."""
    try:
        from agents.controller import AgentController
        # This would use the actual controller in production
        # For now, return a mock response that demonstrates the WebSocket flow
        await asyncio.sleep(0.1)  # Simulate processing
        return f"Processed: {content[:200]}"
    except Exception as e:
        return f"Error processing message: {e}"


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time bi-directional chat.
    
    Protocol:
        → Client sends: {"type": "message", "content": "...", "session_id": "..."}
        ← Server sends: {"type": "token", "content": "...", "index": N}
        ← Server sends: {"type": "done", "tokens": N, "duration_ms": F, "session_id": "..."}
        ← Server sends: {"type": "error", "message": "..."}
    """
    client_id = str(uuid.uuid4())[:8]
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                })
                continue
            
            msg_type = msg.get("type", "message")
            content = msg.get("content", "")
            session_id = msg.get("session_id", f"ws-{client_id}")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                continue
            
            if msg_type == "message" and content:
                start = time.time()
                
                # Send acknowledgment
                await websocket.send_json({
                    "type": "ack",
                    "session_id": session_id,
                    "timestamp": start,
                })
                
                # Process and stream response
                response = await _process_message(content, session_id)
                
                # Stream token by token
                words = response.split()
                for i, word in enumerate(words):
                    await websocket.send_json({
                        "type": "token",
                        "content": word + " ",
                        "index": i + 1,
                    })
                    await asyncio.sleep(0.02)  # Small delay for streaming effect
                
                # Send completion
                duration_ms = (time.time() - start) * 1000
                await websocket.send_json({
                    "type": "done",
                    "tokens": len(words),
                    "duration_ms": round(duration_ms, 1),
                    "session_id": session_id,
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)

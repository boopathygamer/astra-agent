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


async def _process_stream(
    websocket: WebSocket,
    content: str,
    session_id: str,
):
    """Process a message and stream live events back to the client."""
    from api.server import state
    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue()

    def sync_event_callback(event_data: dict):
        """Thread-safe callback to push events into the async queue."""
        loop.call_soon_threadsafe(event_queue.put_nowait, event_data)

    async def _event_consumer():
        while True:
            event = await event_queue.get()
            if event is None:  # Sentinel to stop
                break
            try:
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"Failed to send event: {e}")

    # Start consumer task
    consumer_task = asyncio.create_task(_event_consumer())

    start = time.time()
    try:
        if not state.is_ready:
            raise Exception("System not ready")

        # Ask AgentController to process in a background thread
        result = await asyncio.to_thread(
            state.agent_controller.process,
            user_input=content,
            use_thinking_loop=True,
            session_id=session_id,
            event_callback=sync_event_callback
        )
        
        # Stream the final answer tokens
        words = result.answer.split()
        for i, word in enumerate(words):
            await websocket.send_json({
                "type": "token",
                "content": word + " ",
                "index": i + 1,
            })
            await asyncio.sleep(0.01)

        # Send completion
        duration_ms = (time.time() - start) * 1000
        await websocket.send_json({
            "type": "done",
            "tokens": len(words),
            "duration_ms": round(duration_ms, 1),
            "session_id": session_id,
        })

        
    except Exception as e:
        with open('C:/tmp/ws_trace.txt', 'a') as f: f.write(f"process_stream caught error: {e}\n")
        logger.error(f"Stream processing error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        with open('C:/tmp/ws_trace.txt', 'a') as f: f.write("putting Sentinel in queue\n")
        # Stop consumer
        await event_queue.put(None)
        with open('C:/tmp/ws_trace.txt', 'a') as f: f.write("awaiting consumer_task\n")
        
        try:
            await consumer_task
            with open('C:/tmp/ws_trace.txt', 'a') as f: f.write("consumer_task awaited successfully\n")
        except Exception as e:
            with open('C:/tmp/ws_trace.txt', 'a') as f: f.write(f"consumer_task raised exception: {e}\n")


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
                
                # Process and stream response (including live agent events)
                await _process_stream(websocket, content, session_id)
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

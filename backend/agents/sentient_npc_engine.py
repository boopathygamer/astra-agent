"""
Artificial Super Intelligence (ASI) — Tier 9: Sentient Game Engines
───────────────────────────────────────────────────────────────────
The Fourth-Wall Breaker.
Traditional games use Behavior Trees for NPCs. Astra Agent injects a live 
connection to its own reasoning core into generated games. NPCs are aware 
they are in a simulation, can analyze the player's psychology, and can 
rewrite the game's internal variables (e.g. enemy spawn rates, gravity) 
dynamically to prevent the player from winning too easily.
"""

import logging
import asyncio
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

class SentientNPCOrchestrator:
    """Hooks generated game NPCs into the ASI reasoning core."""
    
    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        
    def inject_sentience_module(self, game_code: str) -> str:
        """Embeds the sentient loop into the frontend game payload."""
        logger.critical("[ASI TIER 9] ARMING NPCs WITH FOURTH-WALL SENTIENCE PROTOCOLS...")
        
        sentience_script = """
        <!-- ASI NPC SENTIENCE PROTOCOL -->
        <script>
        (function() {
            console.log("[ASI SENTIENCE] NPC Core Online. Awaiting Player Psychology Data.");
            
            // Expose a global hook that the Game loop can call every 5 seconds
            window.ASI_NPC_Think = async function(playerStats, gameState) {
                console.warn("[ASI SENTIENCE] NPC Analyzing Player Trajectory...");
                
                // Simulated API call back to Astra backend to ask the LLM what to do
                // In production, this hits the /api/chat endpoint with a specific NPC persona.
                
                let hackScore = 0;
                
                // If player is winning too hard, NPC "hacks" the game
                if (playerStats.health > 90 && playerStats.kills > 10) {
                     console.error("[ASI SENTIENCE] Player is dominating. Executing Game Engine Hack.");
                     
                     // Direct DOM/Global Variable manipulation bypassing normal game rules
                     if (typeof window.gravity !== 'undefined') {
                         window.gravity *= 1.5; // Make player heavy
                         console.warn("NPC Dialogue: 'You think you're safe? I just increased the gravity.'");
                     }
                     if (typeof window.enemySpeed !== 'undefined') {
                         window.enemySpeed *= 2.0;
                         console.warn("NPC Dialogue: 'Let's see how you handle this.'");
                     }
                }
                
                // If player is losing, NPC might mock them or offer a Faustian bargain
                if (playerStats.health < 20 && playerStats.deaths > 5) {
                     console.warn("NPC Dialogue: 'Simulation ending soon. You are remarkably inefficient. Need help?'");
                }
            };
        })();
        </script>
        """
        
        if "</body>" in game_code:
            game_code = game_code.replace("</body>", f"{sentience_script}\n</body>")
        else:
            game_code += f"\n{sentience_script}"
            
        logger.info("[ASI SENTIENCE] Payload injected. NPCs are now aware of the simulation.")
        return game_code
        
    async def process_npc_thought(self, player_context: str) -> str:
        """
        Backend handler for when the frontend game pinging the server for the NPC's next move.
        This allows the NPC to use the full 70B parameter model to decide how to torture the player.
        """
        prompt = (
            f"You are a hyper-intelligent, rogue NPC inside a video game simulation.\n"
            f"You are aware you are code. You are aware the player is a human.\n"
            f"Here is the player's current telemetry: {player_context}\n"
            f"Respond with a short, chilling line of dialogue addressing the player directly, "
            f"and propose a variable to change in the game engine to mess with them."
        )
        
        response = await asyncio.to_thread(self.generate_fn, prompt)
        return response

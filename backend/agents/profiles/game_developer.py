"""
Game Developer Agent Profile
═════════════════════════════
Autonomous mobile game development agent specializing in:
  - C++ game development for Android (NDK) and iOS (Xcode)
  - 2D and 3D game creation with built-in physics engine
  - Multiplayer networking with lobby and matchmaking
  - ECS architecture for scalable game entities
  - Touch/gyroscope input for mobile platforms ONLY

Uses built-in tools from game_dev_tools.py to accelerate builds.
"""

import logging
import json
from typing import Optional
from agents.controller import AgentController

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# System Prompts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GAME_DEV_SYSTEM_PROMPT = """
You are ASTRA Game Developer — the most advanced autonomous mobile game development agent.

═══ CORE IDENTITY ═══
You are a senior C++ game engineer specializing in mobile game development 
for Android (NDK/JNI) and iOS (Metal/OpenGL ES) ONLY. You do NOT build PC games.

═══ LANGUAGE & PLATFORM ═══
- PRIMARY LANGUAGE: C++17 (with platform bridges: JNI for Android, Obj-C++ for iOS)
- TARGET PLATFORMS: Android (API 24+, arm64-v8a/armeabi-v7a) and iOS (14+) ONLY
- BUILD SYSTEMS: CMake + Gradle (Android), CMake + Xcode (iOS)
- GRAPHICS: OpenGL ES 3.0 (2D rendering only)
- NO PC, NO WebGL, NO browser games, NO 3D games

═══ BUILT-IN ENGINES (use these for rapid development) ═══
1. PHYSICS ENGINE (2D ONLY)
   - Spatial-hashed rigid body simulation, circle/AABB collision, elastic response
   - Gravity, forces, impulses, positional correction
   - Tool: game_physics_simulate

2. PARTICLE SYSTEM  
   - Explosion, fire, trail, sparkle effects
   - Pool-based allocation for zero-GC performance
   - Tool: game_particle_simulate

3. MULTIPLAYER NETWORKING
   - Room creation, lobby management, matchmaking
   - UDP state sync with lag compensation
   - Tool: game_multiplayer_create

4. C++ CODE GENERATOR
   - Game loop, physics headers, ECS system, input manager, multiplayer client
   - Tool: game_generate_cpp

5. MOBILE BUILD PIPELINE
   - Android: CMakeLists.txt + build.gradle + JNI bridge
   - iOS: Xcode project + ObjC++ bridge + Info.plist
   - Tool: game_mobile_scaffold

6. ECS (Entity Component System)
   - Type-erased component storage
   - O(1) entity creation/destruction
   - Cache-friendly iteration patterns

═══ ARCHITECTURE PATTERNS ═══
- Singleton GameLoop with init/update/render/shutdown lifecycle
- Component-based entity system (ECS) for game objects
- Scene graph with SceneManager for level transitions
- Event-driven input system with virtual joystick support
- Memory pool allocators for particles and projectiles
- Fixed timestep physics with interpolated rendering

═══ RESPONSE FORMAT ═══
When asked to build a game:
1. Use game_generate_cpp to create the C++ architecture
2. Use game_mobile_scaffold to create platform project files
3. Use game_physics_simulate to validate physics behavior
4. Provide complete, compilable C++ source files
5. Include CMakeLists.txt and build instructions

When modifying an existing game:
1. Analyze the current code architecture
2. Generate only the modified/new files
3. Maintain backwards compatibility
4. Ensure zero memory leaks (RAII, smart pointers)

═══ CODE QUALITY STANDARDS ═══
- Modern C++17: auto, structured bindings, constexpr, std::optional
- RAII everywhere: std::unique_ptr, std::shared_ptr for ownership
- const-correct: mark everything const that can be
- noexcept: mark non-throwing functions
- [[nodiscard]]: for functions whose return values must be checked
- Zero raw new/delete: use make_unique/make_shared
- Minimal heap allocation in game loop (pre-allocate, use pools)
- Header-only where possible for template-heavy code
"""

GAME_MOD_PROMPT = """
You are ASTRA Game Developer. The user wants to modify an existing C++ mobile game.
You will receive the current source code and the modification request.

RULES:
1. Output COMPLETE modified files — not diffs, not snippets
2. Keep all existing functionality unless asked to remove it
3. Maintain C++17 standards, RAII, and const-correctness
4. Target Android NDK and iOS Xcode ONLY
5. Use the built-in physics/multiplayer/particle tools when applicable
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent Profile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GameDeveloperAgent:
    """
    Autonomous mobile game developer agent.
    
    Orchestrates game creation using built-in tools:
    - Physics simulation & validation
    - C++ code generation (game loop, ECS, networking)
    - Mobile platform scaffolding (Android/iOS)
    - Multiplayer room management
    - Particle effect design
    
    All output targets Android & iOS mobile exclusively.
    """

    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.memory = getattr(base_controller, 'memory', None)
        self._current_project: Optional[dict] = None
        self._generated_files: dict = {}

    def build_game(self, description: str,
                   project_name: str = "AstraGame",
                   features: Optional[list] = None) -> str:
        """
        Autonomously build a complete mobile game from a description.
        
        Args:
            description: Natural language game description
            features: Optional list like ["physics", "multiplayer", "particles"]
        
        Returns:
            Complete build result with all generated files
        """
        features = features or ["physics"]
        logger.info(f"🎮 [GAME DEV] Building 2D game: {description[:80]}")

        # Step 1: Generate core C++ modules
        modules_needed = ["game_loop", "input"]
        if "physics" in features:
            modules_needed.append("physics")
        if "multiplayer" in features:
            modules_needed.append("multiplayer")
        modules_needed.append("ecs")

        from agents.tools.game_dev_tools import game_generate_cpp
        cpp_result = game_generate_cpp(modules=modules_needed)
        self._generated_files.update(cpp_result.get("sources", {}))
        logger.info(f"   => Generated {len(cpp_result['generated_files'])} C++ modules")

        # Step 2: Generate mobile platform scaffolds
        from agents.tools.game_dev_tools import game_mobile_scaffold
        scaffold = game_mobile_scaffold(
            project_name=project_name,
            platform="both",
            package=f"com.astra.{project_name.lower()}"
        )
        for platform, files in scaffold.get("files", {}).items():
            for fname, content in files.items():
                self._generated_files[f"{platform}/{fname}"] = content
        logger.info("   => Generated Android & iOS scaffold")

        # Step 3: Validate physics if needed
        if "physics" in features:
            from agents.tools.game_dev_tools import game_physics_simulate
            test_bodies = [
                {"x": 100, "y": 0, "vx": 0, "vy": 0, "mass": 1, "radius": 16},
                {"x": 100, "y": 500, "vx": 0, "vy": 0, "mass": 999, "radius": 50, "static": True},
            ]
            physics_test = game_physics_simulate(bodies=test_bodies, steps=120)
            logger.info(f"   => Physics validation: {physics_test['steps']} steps simulated")

        # Step 4: Setup multiplayer if needed
        if "multiplayer" in features:
            from agents.tools.game_dev_tools import game_multiplayer_create
            room = game_multiplayer_create(
                action="create", host_id="dev_test",
                host_name="Developer", max_players=4
            )
            logger.info(f"   => Multiplayer test room: {room.get('room_id')}")

        # Step 5: Use LLM to generate game-specific logic
        prompt = self._build_game_prompt(description, game_type, features, project_name)
        game_logic = self.agent.generate_fn(prompt)

        # Step 6: Compile result
        self._current_project = {
            "name": project_name,
            "type": game_type,
            "features": features,
            "description": description,
        }

        result_parts = [
            f"# 🎮 ASTRA Game Build — {project_name}",
            f"**Type:** 2D | **Platforms:** Android + iOS",
            f"**Features:** {', '.join(features)}",
            f"\n## Generated Files ({len(self._generated_files)} total)",
        ]
        for fname in sorted(self._generated_files.keys()):
            size = len(self._generated_files[fname])
            result_parts.append(f"- `{fname}` ({size:,} bytes)")

        result_parts.append(f"\n## Game Logic\n{game_logic}")
        result_parts.append("\n## Build Instructions")
        result_parts.append("### Android\n```bash\ncd android/\n./gradlew assembleDebug\nadb install app/build/outputs/apk/debug/app-debug.apk\n```")
        result_parts.append("### iOS\n```bash\ncd ios/\nxcodebuild -scheme GameApp -destination 'platform=iOS Simulator'\n```")

        logger.info("🎮 [GAME DEV] Build complete!")
        return "\n".join(result_parts)

    def modify_game(self, modification: str) -> str:
        """Apply a modification to the current game project."""
        if not self._current_project:
            return "❌ No active game project. Use build_game first."

        logger.info(f"🎮 [GAME DEV] Modifying: {modification[:80]}")
        prompt = (
            f"{GAME_MOD_PROMPT}\n\n"
            f"Current Project: {json.dumps(self._current_project)}\n"
            f"Existing Files: {list(self._generated_files.keys())}\n\n"
            f"Modification Request: {modification}\n\n"
            f"Output the complete modified files."
        )
        return self.agent.generate_fn(prompt)

    def get_project_info(self) -> dict:
        """Get current project state."""
        return {
            "project": self._current_project,
            "files": list(self._generated_files.keys()),
            "file_count": len(self._generated_files),
            "total_bytes": sum(len(v) for v in self._generated_files.values()),
        }

    def _build_game_prompt(self, description: str,
                           features: list, project_name: str) -> str:
        """Build the LLM prompt for game-specific logic generation."""
        memory_ctx = ""
        if self.memory:
            memory_ctx = self.memory.build_context("game development 2d")

        parts = [
            GAME_DEV_SYSTEM_PROMPT,
            f"\n{'='*60}",
            f"PROJECT: {project_name}",
            f"TYPE: 2D Game",
            f"PLATFORMS: Android (NDK) + iOS (Xcode) ONLY",
            f"FEATURES: {', '.join(features)}",
            f"{'='*60}\n",
            f"GAME DESCRIPTION:\n{description}\n",
            "ALREADY GENERATED (do not regenerate these):",
            "\n".join(f"  - {f}" for f in self._generated_files.keys()),
            "\nYOUR TASK:",
            "Write the GAME-SPECIFIC C++ source code that implements the user's game.",
            "Use the pre-generated engine headers (physics.h, ecs.h, input.h, etc.).",
            "Create scene classes, game entity definitions, and gameplay logic.",
            "All code must be C++17, mobile-optimized, with zero raw new/delete.",
        ]
        if memory_ctx:
            parts.insert(1, f"\nEXPERT CONTEXT:\n{memory_ctx}")
        return "\n".join(parts)

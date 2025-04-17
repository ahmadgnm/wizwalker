import asyncio
from wizwalker import ClientHandler, XYZ
from typing import List, Optional, Dict
import math
import json
import os
from pathlib import Path
import subprocess
import sys
import socket
import datetime

class LocationTracker:
    """Tracks and manages game locations and landmarks"""
    def __init__(self):
        self.data_file = Path("location_data.json")
        self.locations = self._load_data()
    
    def _load_data(self):
        """Load saved location data"""
        if self.data_file.exists():
            try:
                return json.loads(self.data_file.read_text())
            except:
                return {}
        return {}
    
    def _save_data(self):
        """Save location data to file"""
        self.data_file.write_text(json.dumps(self.locations, indent=2))
    
    def update_location(self, zone: str, x: float, y: float, z: float):
        """Record a visited location"""
        if zone not in self.locations:
            self.locations[zone] = {
                "areas": {},
                "landmarks": []
            }
        
        # Add coordinates to area mapping
        area_key = f"{int(x//100)},{int(y//100)}"
        if area_key not in self.locations:
            self.locations[zone]["areas"][area_key] = {
                "min_x": x, "max_x": x,
                "min_y": y, "max_y": y,
                "visits": 0
            }
        
        area = self.locations[zone]["areas"][area_key]
        area["min_x"] = min(area["min_x"], x)
        area["max_x"] = max(area["max_x"], x)
        area["min_y"] = min(area["min_y"], y)
        area["max_y"] = max(area["max_y"], y)
        area["visits"] += 1
        
        self._save_data()
    
    def get_location_info(self, zone: str, x: float, y: float, z: float) -> dict:
        """Get location details for coordinates"""
        if zone not in self.locations:
            return {"area": "Unknown Area", "landmark": None}
            
        # Find matching area
        area_key = f"{int(x//100)},{int(y//100)}"
        if area_key in self.locations[zone]["areas"]:
            area = self.locations[zone]["areas"][area_key]
        else:
            area = {"area": "Unexplored Area"}
            
        # Find nearest landmark
        nearest_landmark = None
        min_dist = float('inf')
        for landmark in self.locations[zone]["landmarks"]:
            dist = math.sqrt(
                (x - landmark["x"])**2 + 
                (y - landmark["y"])**2
            )
            if dist < min_dist:
                min_dist = dist
                nearest_landmark = landmark
                
        return {
            "area": area.get("name", "Unknown Area"),
            "landmark": nearest_landmark["name"] if nearest_landmark and min_dist < 50 else None
        }

# Initialize the location tracker at the module level
location_tracker = LocationTracker()

# Add these functions at the top level of the file
def get_location_info(x: float, y: float, z: float) -> dict:
    """
    Get detailed location information based on coordinates
    """
    locations = {
        # Wizard City - Commons
        (-500, -200, -200, 200): {
            "zone": "WizardCity/WC_Streets",
            "area": "Commons",
            "landmarks": {
                (-400, -350, -50, 0): "Library",
                (-450, -400, 50, 100): "Commons Fountain",
            }
        },
        # Wizard City - Ravenwood
        (200, 500, -200, 200): {
            "zone": "WizardCity/WC_Hub",
            "area": "Ravenwood",
            "landmarks": {
                (250, 300, -50, 0): "Fire School",
                (350, 400, 50, 100): "Ice School",
            }
        },
        # Death School
        (300, 600, -100, 100): {
            "zone": "WizardCity/Interiors/WC_SchoolDeath",
            "area": "Death School",
            "landmarks": {
                (400, 500, -50, 50): "Death School Classroom",
            }
        }
    }
    
    result = {
        "zone": "Unknown Zone",
        "area": "Unknown Area",
        "landmark": "No nearby landmarks"
    }
    
    # Find matching zone
    for (x1, x2, y1, y2), info in locations.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            result["zone"] = info["zone"]
            result["area"] = info["area"]
            
            # Check landmarks
            for (lx1, lx2, ly1, ly2), landmark in info["landmarks"].items():
                if lx1 <= x <= lx2 and ly1 <= y <= ly2:
                    result["landmark"] = landmark
                    break
            break
    
    return result

# --- Extend Client with enhanced methods ---
async def get_quest_objectives(self):
    """
    Retrieves the current quest objective's position.
    """
    try:
        position = await self.quest_position.position()
        return [position]
    except Exception as e:
        print(f"Error retrieving quest objective position: {e}")
        return []

async def auto_dialog(self):
    """
    Automatically handles NPC dialog by advancing through it
    """
    while await self.is_in_dialog():
        try:
            await self.send_key(0x1B, 0.1)  # Press ESC
            await asyncio.sleep(0.2)
        except Exception as e:
            print(f"Dialog handling error: {e}")
            break

async def get_closest_mob(self):
    """
    Finds the closest enemy mob for combat
    """
    try:
        mobs = await self.get_mobs()
        if not mobs:
            return None
        
        player_pos = await self.body.position()
        closest_mob = None
        min_distance = float('inf')
        
        for mob in mobs:
            mob_pos = await mob.position()
            distance = math.sqrt(
                (player_pos.x - mob_pos.x) ** 2 +
                (player_pos.y - mob_pos.y) ** 2
            )
            if distance < min_distance:
                min_distance = distance
                closest_mob = mob
                
        return closest_mob
    except Exception as e:
        print(f"Error finding closest mob: {e}")
        return None

async def detect_battle_state(self):
    """More accurate battle state detection"""
    try:
        # First check if we're in battle at all
        in_combat = await self.in_battle()
        
        if not in_combat:
            return "not_in_battle"
        
        # Since we're in battle, check the duel phase
        try:
            duel_phase = str(await self.duel.duel_phase())
            
            # Check specifically for DuelPhase.execution
            if duel_phase == "DuelPhase.execution":
                return "playing_animation"
            else:
                return "planning"
                
        except Exception as e:
            print(f"Error getting duel phase: {e}")
            return "in_battle"
            
    except Exception as e:
        print(f"Battle detection error: {e}")
        return "unknown"

from wizwalker.client_handler import Client
Client.get_quest_objectives = get_quest_objectives
Client.auto_dialog = auto_dialog
Client.get_closest_mob = get_closest_mob
Client.detect_battle_state = detect_battle_state

def log_battle_event(msg: str):
    with open("battle_monitor.log", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {msg}\n")

class EnhancedWizWalker(ClientHandler):
    def __init__(self, speed_multiplier: float = 1.0):
        super().__init__()
        self.speed_multiplier = speed_multiplier
        self.battle_speed_multiplier = 3.0  # Default battle speed
        self.fast_battles_enabled = False
        self.current_battle_state = "not_in_battle"
        self.running = True
        self.clients = []
        self._battle_task = None
        self.monitor_process = None

    def start_battle_monitor(self):
        """Start the battle monitor log viewer in a new terminal window."""
        if getattr(self, "monitor_process", None) and self.monitor_process.poll() is None:
            # Already running
            return
        bat_path = os.path.join(os.path.dirname(__file__), "battle_monitor.py")
        cmd = f'start "Battle Monitor" cmd /k python "{bat_path}"'
        self.monitor_process = subprocess.Popen(cmd, shell=True)

    def stop_battle_monitor(self):
        """Close the battle monitor log viewer window."""
        if getattr(self, "monitor_process", None):
            try:
                self.monitor_process.terminate()
            except Exception:
                pass
            self.monitor_process = None

    async def _monitor_battles(self):
        was_in_battle = False
        last_state = None
        last_speed = None  # Track actual applied speed

        while self.running and self.fast_battles_enabled:
            try:
                for client in self.clients:
                    current_state = await client.detect_battle_state()
                    duel_phase = None
                    try:
                        duel_phase = await client.duel.duel_phase()
                    except Exception:
                        duel_phase = "Unknown"

                    # Log every state change
                    if current_state != last_state:
                        log_battle_event(f"Battle state changed: {current_state} (duel_phase={duel_phase})")
                        last_state = current_state

                    # Aggressively set speed during animation phase
                    if current_state != "not_in_battle":
                        if not was_in_battle:
                            log_battle_event("Battle began!")
                            was_in_battle = True

                        # Animation phase: set battle speed every loop
                        if current_state == "playing_animation":
                            await self.apply_speed(self.battle_speed_multiplier, client, silent=True)
                            log_battle_event(f"Set speed to {self.battle_speed_multiplier}x (animation phase)")
                            last_speed = self.battle_speed_multiplier
                        # Planning phase: set normal speed every loop
                        elif current_state == "planning":
                            await self.apply_speed(self.speed_multiplier, client, silent=True)
                            log_battle_event(f"Set speed to {self.speed_multiplier}x (planning phase)")
                            last_speed = self.speed_multiplier

                    elif was_in_battle:
                        log_battle_event("Battle ended!")
                        was_in_battle = False
                        await self.apply_speed(self.speed_multiplier, client, silent=True)
                        last_speed = self.speed_multiplier

                await asyncio.sleep(0.05 if was_in_battle else 0.5)

            except Exception as e:
                log_battle_event(f"Monitor error: {e}")
                await asyncio.sleep(0.2)

    async def toggle_fast_battles(self, enabled: Optional[bool] = None):
        if enabled is None:
            self.fast_battles_enabled = not self.fast_battles_enabled
        else:
            self.fast_battles_enabled = enabled

        status = "enabled" if self.fast_battles_enabled else "disabled"
        print(f"\nFast battles {status}")

        if self.fast_battles_enabled:
            self.start_battle_monitor()
            if not self._battle_task or self._battle_task.done():
                self._battle_task = asyncio.create_task(self._monitor_battles())
        else:
            if self._battle_task:
                self._battle_task.cancel()
            self.stop_battle_monitor()
            for client in self.clients:
                await self.apply_speed(self.speed_multiplier, client)

    async def apply_speed(self, speed_value: float, client=None, silent=False):
        """Aggressively apply speed to ensure it takes effect."""
        try:
            target_speed = int(speed_value * 100)
            clients_to_update = [client] if client else self.clients
            for c in clients_to_update:
                try:
                    await c.client_object.write_speed_multiplier(target_speed)
                    # Try memory write if available
                    if hasattr(c.client_object, 'speed_multiplier_address'):
                        addr = c.client_object.speed_multiplier_address
                        if hasattr(c.client_object, 'write_typed'):
                            await c.client_object.write_typed(addr, target_speed, "int")
                    if not silent:
                        print(f"Applied speed {speed_value}x to client")
                except Exception as e:
                    if not silent:
                        print(f"Speed application error: {e}")
            return True
        except Exception as e:
            if not silent:
                print(f"Apply speed error: {e}")
            return False

    async def close(self, reset_speed=True):
        """Clean up and close connections"""
        print("Cleaning up...")
        
        # Cancel battle monitor task
        if self._battle_task:
            self._battle_task.cancel()
            try:
                await self._battle_task
            except asyncio.CancelledError:
                pass
            self._battle_task = None

        # Clean up clients
        if hasattr(self, 'clients'):
            for client in self.clients:
                try:
                    # Force deactivate all hooks
                    if hasattr(client, 'hook_handler'):
                        for hook in client.hook_handler.hooks.values():
                            try:
                                if hasattr(hook, 'deactivate'):
                                    await hook.deactivate()
                            except:
                                pass
                        client.hook_handler.hooks.clear()

                    # Reset speed before cleanup
                    if reset_speed:
                        try:
                            await client.client_object.write_speed_multiplier(100)
                        except:
                            pass
                            
                except Exception as e:
                    print(f"Error cleaning up client hooks: {e}")

        # Call parent cleanup
        try:
            await super().close()
        except Exception as e:
            print(f"Error in parent close: {e}")
            
        self.clients = []
        print("Cleanup complete")

    async def start(self):
        """Connect to clients and activate hooks"""
        # Clean up existing hooks
        await self.close(reset_speed=False)
        await asyncio.sleep(1.0)  # Wait for cleanup
        
        # Get fresh clients
        self.get_new_clients()
        if not self.clients:
            print("No Wizard101 clients found. Please start the game first.")
            return False

        try:
            # Wait for hooks to fully deactivate
            await asyncio.sleep(0.5)
            
            # Activate new hooks safely
            for client in self.clients:
                try:
                    await client.activate_hooks()
                    # Don't try to activate duel hooks directly
                except Exception as e:
                    print(f"Warning: Could not activate hooks for client: {e}")
                    continue
            
            if self.speed_multiplier != 1.0:
                await self.speed_up()
            
            self._battle_task = asyncio.create_task(self._monitor_battles())
            return True
            
        except Exception as e:
            print(f"Error activating hooks: {e}")
            await self.close()
            return False

    async def set_speed(self, speed: float):
        """Set game speed"""
        try:
            self.speed_multiplier = speed
            await self.speed_up()
        except Exception as e:
            print(f"Error setting speed: {e}")

    async def speed_up(self):
        """Apply speed multiplier to all clients"""
        for client in self.clients:
            await client.client_object.write_speed_multiplier(int(self.speed_multiplier * 100))

    async def send_to_monitor(self, message_type: str, **data):
        """Send update to battle monitor"""
        if self.monitor_writer:
            try:
                message = {"type": message_type, **data}
                self.monitor_writer.write(
                    json.dumps(message).encode() + b'\n'
                )
                await self.monitor_writer.drain()
            except Exception as e:
                print(f"Error sending to monitor: {e}")

# Add restart function
def restart_script():
    """Completely restart the script"""
    print("\nRestarting script...")
    subprocess.Popen([sys.executable, sys.argv[0]])
    sys.exit(0)

async def main():
    walker = None
    try:
        walker = EnhancedWizWalker(2.0)
        print("\nConnecting to Wizard101...")
        if not await walker.start():
            return

        client = walker.clients[0] if walker.clients else None
        print("\nType 'help' for commands")

        while walker.running:
            try:
                command = input("\nWizWalker> ").strip().lower()
                parts = command.split()
                if not parts:
                    continue
                cmd = parts[0]
                args = parts[1:]

                if cmd == "exit":
                    walker.running = False
                elif cmd == "help":
                    print("\nAvailable Commands:")
                    print("- info: Show detailed client info (status, quests, etc.)")
                    print("- teleport/goto x y z: Teleport to coordinates")
                    print("- gotoquest: Teleport to quest objective")
                    print("- quest: Show quest info")
                    print("- speed x: Set speed multiplier")
                    print("- fastbattles/fb [on|off]: Toggle fast battle animations")
                    print("- battlespeed/bs [speed]: Set battle animation speed")
                    print("- battledebug: Debug battle detection")
                    print("- forcespeed x: Force specific game speed")
                    print("- restart: Restart the script")
                    print("- exit: Exit program")
                elif cmd == "info":
                    if client:
                        try:
                            # Basic information
                            zone = await client.zone_name()
                            pos = await client.body.position()
                            
                            # Client status
                            in_battle = await client.in_battle()
                            in_dialog = await client.is_in_dialog()
                            in_npc_range = await client.is_in_npc_range()
                            is_loading = await client.is_loading()
                            
                            # Quest information
                            quest_id = await client.quest_id()
                            goal_id = await client.goal_id()
                            
                            print("\n=== Client Information ===")
                            print(f"Zone: {zone}")
                            print(f"Position: {pos}")
                            print(f"Loading: {is_loading}")
                            print(f"Speed: {walker.speed_multiplier}x")
                            
                            print("\n=== Status ===")
                            print(f"In Battle: {in_battle}")
                            print(f"In Dialog: {in_dialog}")
                            print(f"In NPC Range: {in_npc_range}")
                            
                            print("\n=== Quest ===")
                            print(f"Quest ID: {quest_id}")
                            print(f"Goal ID: {goal_id}")
                            
                            if in_battle:
                                try:
                                    duel_phase = await client.duel.duel_phase()
                                    print(f"Duel Phase: {duel_phase}")
                                except:
                                    print("Duel details unavailable")
                        except Exception as e:
                            print(f"Error getting client info: {e}")
                    else:
                        print("No client connected")
                elif cmd in ["teleport", "goto"]:
                    if not client or len(args) < 2:
                        print("Usage: goto x y [z]")
                        continue
                    try:
                        x, y = float(args[0]), float(args[1])
                        z = float(args[2]) if len(args) > 2 else 0.0
                        await client.teleport(XYZ(x, y, z))
                    except ValueError:
                        print("Invalid coordinates")
                elif cmd == "gotoquest":
                    if client:
                        objectives = await client.get_quest_objectives()
                        if objectives:
                            for obj in objectives:
                                await client.teleport(obj)
                                print(f"Teleported to {obj}")
                        else:
                            print("No quest objectives found")
                elif cmd == "quest":
                    if client:
                        try:
                            quest_id = await client.quest_id()
                            objectives = await client.get_quest_objectives()
                            current_pos = await client.body.position()
                            current_zone = await client.zone_name()
                            
                            # Update location data
                            location_tracker.update_location(
                                current_zone,
                                current_pos.x,
                                current_pos.y,
                                current_pos.z
                            )
                            
                            print("\nQuest Information:")
                            print(f"ID: {quest_id}")
                            
                            if objectives:
                                print("\nObjectives:")
                                for idx, obj in enumerate(objectives, 1):
                                    try:
                                        # Calculate distance
                                        distance = math.sqrt(
                                            (obj.x - current_pos.x) ** 2 +
                                            (obj.y - current_pos.y) ** 2
                                        )
                                        # Get location info
                                        loc_info = location_tracker.get_location_info(
                                            current_zone,
                                            obj.x,
                                            obj.y,
                                            obj.z
                                        )
                                        print(f"\nObjective {idx}:")
                                        print(f"  Zone: {current_zone}")
                                        print(f"  Area: {loc_info['area']}")
                                        if loc_info['landmark']:
                                            print(f"  Near: {loc_info['landmark']}")
                                        print(f"  Position: <{obj.x:.1f}, {obj.y:.1f}, {obj.z:.1f}>")
                                        print(f"  Distance: {distance:.1f} units")
                                        
                                        # Add direction indicator
                                        dx = obj.x - current_pos.x
                                        dy = obj.y - current_pos.y
                                        direction = ""
                                        if abs(dx) > abs(dy) * 2:
                                            direction = "East" if dx > 0 else "West"
                                        elif abs(dy) > abs(dx) * 2:
                                            direction = "North" if dy > 0 else "South"
                                        else:
                                            ns = "North" if dy > 0 else "South"
                                            ew = "East" if dx > 0 else "West"
                                            direction = f"{ns}-{ew}"
                                        print(f"  Direction: {direction}")
                                    except Exception as e:
                                        print(f"Error displaying objective {idx}: {e}")
                            else:
                                print("\nNo quest objectives found")
                        except Exception as e:
                            print(f"Error getting quest details: {e}")
                elif cmd in ["fastbattles", "fb"]:
                    if args:
                        enabled = args[0].lower() == "on"
                        await walker.toggle_fast_battles(enabled)
                    else:
                        await walker.toggle_fast_battles()
                elif cmd in ["battlespeed", "bs"]:
                    if args:
                        try:
                            speed = float(args[0])
                            if speed >= 1.0:  # Only enforce minimum speed
                                walker.battle_speed_multiplier = speed
                                print(f"Battle animation speed set to {speed}x")
                            else:
                                print("Speed must be 1.0 or higher")
                        except ValueError:
                            print("Invalid speed value")
                    else:
                        print(f"Current battle animation speed: {walker.battle_speed_multiplier}x")
                        print("Usage: battlespeed <speed>")

                elif cmd == "forcespeed":
                    if client and args:
                        try:
                            speed = float(args[0])
                            print(f"Forcing client speed to {speed}x")
                            await client.client_object.write_speed_multiplier(int(speed * 100))
                        except Exception as e:
                            print(f"Error setting forced speed: {e}")
                    else:
                        print("Usage: forcespeed <multiplier>")
                elif cmd == "restart":
                    print("Performing full script restart")
                    if walker:
                        await walker.close()
                    restart_script()
                elif cmd == "startbm":
                    if walker.fast_battles_enabled:
                        if walker._battle_task and not walker._battle_task.done():
                            print("Battle monitor is already running")
                        else:
                            walker._battle_task = asyncio.create_task(walker._monitor_battles())
                            print("Battle monitor manually started")
                    else:
                        print("Enable fast battles first with 'fb on'")
                elif cmd == "testspeed":
                    if client and args:
                        try:
                            speed = float(args[0])
                            print(f"Testing direct speed write: {speed}x")
                            await walker.apply_speed(speed, client)
                        except Exception as e:
                            print(f"Error in direct speed test: {e}")
                    else:
                        print("Usage: testspeed <multiplier>")
            except Exception as e:
                print(f"Command error: {e}")
    except Exception as e:
        print(f"Main error: {e}")
    finally:
        if walker:
            await walker.close()
        print("Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
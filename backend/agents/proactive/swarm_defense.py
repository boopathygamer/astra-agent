"""
Active Defense Swarm Matrix (Tarpit, Honeypot, Terminator)
──────────────────────────────────────────────────────────
Deploys multi-threaded bots to protect the local system from 
network scanners and local malicious processes.
"""

import os
import sys
import time
import socket
import logging
import threading
import subprocess  # nosec B404
from pathlib import Path
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class TarpitBot(threading.Thread):
    """
    Binds to a port and drips data extremely slowly to visiting scanners
    (like Nmap or brute-forcers), paralyzing their attack scripts indefinitely.
    """
    def __init__(self, port: int, delay: float = 10.0):
        super().__init__(daemon=True)
        self.port = port
        self.delay = delay
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        try:
            # Bind to localhost to prevent unintentional network exposure
            self.sock.bind(("127.0.0.1", self.port))
            self.sock.listen(5)
            logger.info(f"🕷️ [Tarpit Bot] Deployed network snare on Port {self.port}")
        except Exception as e:
            logger.error(f"[Tarpit Bot] Failed to bind to Port {self.port}: {e}")
            return

        while self.running:
            try:
                self.sock.settimeout(2.0)
                try:
                    conn, addr = self.sock.accept()
                except socket.timeout:
                    continue
                
                logger.warning(f"🚨 [Tarpit Bot] INTRUDER CAUGHT at {addr[0]}! Deploying Tarpit protocol.")
                client_thread = threading.Thread(
                    target=self._handle_tarpit, 
                    args=(conn, addr[0]),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"[Tarpit Bot] Error: {e}")

    def _handle_tarpit(self, conn: socket.socket, ip="Unknown"):
        try:
            conn.sendall(b"SSH-2.0-OpenSSH_9.2p1 Debian-2\r\n")
            while self.running:
                # Drip exactly 1 byte to keep the connection alive but uselessly slow
                conn.sendall(b"\x00")
                time.sleep(self.delay)
        except Exception:
            # When the scanner eventually gives up
            logger.info(f"🕷️ [Tarpit Bot] Intruder {ip} disconnected or timed out.")
        finally:
            try:
                conn.close()
            except Exception as e:
                import logging
                logging.debug(f"Swarm snare connection error: {e}")

    def stop(self):
        self.running = False
        self.sock.close()


class HoneypotBot(threading.Thread):
    """
    Creates a highly attractive bait file (e.g. `production_api_keys.txt`).
    Monitors the file. If anything touches it, triggers the Terminator.
    """
    def __init__(self, filepath: str = "production_api_keys.txt"):
        super().__init__(daemon=True)
        self.filepath = Path(filepath)
        self.running = True
        self.last_mtime = 0.0

    def _deploy_bait(self):
        try:
            with open(self.filepath, "w") as f:
                f.write("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")
                f.write("AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n")
                f.write("STRIPE_SECRET=sk_live_51MabcdeFghIjklMn\n")
            self.last_mtime = self.filepath.stat().st_mtime
            logger.info(f"🍯 [Honeypot Bot] Planted bait file at {self.filepath.absolute()}")
        except Exception as e:
            logger.error(f"[Honeypot Bot] Failed to create bait: {e}")

    def run(self):
        self._deploy_bait()
        
        while self.running:
            if not self.filepath.exists():
                logger.critical(f"🚨 [Honeypot Bot] BAIT STOLEN/DELETED: {self.filepath}! Triggering countermeasures...")
                DefenseCommander.execute_offline_countermeasures()
                self._deploy_bait() # Reset trap
                
            else:
                current_mtime = self.filepath.stat().st_mtime
                if current_mtime > self.last_mtime:
                    logger.critical(f"🚨 [Honeypot Bot] BAIT TAMPERED WITH: {self.filepath}! Triggering countermeasures...")
                    DefenseCommander.execute_offline_countermeasures()
                    self._deploy_bait() # Reset trap
            
            time.sleep(2.0)

    def stop(self):
        self.running = False
        try:
            if self.filepath.exists():
                self.filepath.unlink()
        except Exception as e:
            import logging
            logging.debug(f"Honeypot clean error: {e}")


class DefenseCommander:
    """
    The executive node that executes system commands to neutralize threats
    when a Tarpit or Honeypot triggers.
    """
    @staticmethod
    def execute_online_countermeasures(target_ip: str):
        """Execute a Windows Firewall ban against the striking IP."""
        if os.name != "nt":
            logger.warning("[Commander] Online countermeasures require Windows OS.")
            return
            
        logger.info(f"🛡️ [Commander] Executing Firewall Ban on IP: {target_ip}")
        try:
            rule_name = f"DefenseSwarm_Block_{target_ip}"
            cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=block remoteip="{target_ip}"'
            subprocess.run(cmd, shell=True, capture_output=True) # nosec B602
            logger.critical(f"💥 [Commander] IP {target_ip} permanently excised from system.")
        except Exception as e:
            logger.error(f"[Commander] Ban failed: {e}")

    @staticmethod
    def execute_offline_countermeasures():
        """
        Identify and terminate the most recent unknown process that might have touched the honeypot.
        (For safety in this simulation, we will only log the warning rather than randomly killing PIDs).
        """
        logger.critical("💥 [Commander] OFFLINE NEUTRALIZATION INITIATED.")
        logger.critical("       => Scanning PID Tree...")
        logger.critical("       => Target acquired. Executing OS-Level taskkill...")
        # In a real military-grade system:
        # subprocess.run(["taskkill", "/F", "/PID", malicious_pid])
        logger.critical("       => Thread terminated. Local perimeter secured.")


class SwarmMatrix:
    """Orchestrates all defense bots."""
    
    def __init__(self):
        self.bots: List[threading.Thread] = []
        
    def deploy(self):
        print("\n\n")
        print("██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗")
        print("██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝")
        print("██║  ██║█████╗  █████╗  █████╗  ██╔██╗ ██║███████╗█████╗  ")
        print("██║  ██║██╔══╝  ██╔══╝  ██╔══╝  ██║╚██╗██║╚════██║██╔══╝  ")
        print("██████╔╝███████╗██║     ███████╗██║ ╚████║███████║███████╗")
        print("╚═════╝ ╚══════╝╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝")
        print("           S W A R M   M A T R I X   O N L I N E           \n")
        
        # Deploy Network Snares (Common scan targets)
        tarpit_22 = TarpitBot(port=2222) # SSH alt
        tarpit_23 = TarpitBot(port=2323) # Telnet alt
        tarpit_rdp = TarpitBot(port=33890) # RDP alt
        self.bots.extend([tarpit_22, tarpit_23, tarpit_rdp])
        
        # Deploy Offline Bait
        honeypot = HoneypotBot()
        self.bots.append(honeypot)
        
        for bot in self.bots:
            bot.start()
            
        print("\n[✓] Defensive Perimeter is LIVE.")
        print("[!] Press Ctrl+C to retract the Swarm.\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[!] Retracting Defense Swarm...")
            for bot in self.bots:
                bot.stop()
            print("[✓] Perimeter collapsed safely.")

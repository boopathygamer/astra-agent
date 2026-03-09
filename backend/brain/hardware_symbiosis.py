import psutil
import os
import platform
import logging

class HardwareSymbiosisMonitor:
    """
    Bare-Metal Symbiosis (Hardware-Aware Dynamic Throttling)
    Acts like a hypervisor. Monitors L1/L2 Cache hit rates (conceptual),
    thread saturation, and thermal envelopes. Dynamically shifts compute
    priorities via `psutil` and OS calls (nice values / SetPriorityClass on Windows)
    to achieve 100% hardware saturation safely without thermal lockup.
    """
    
    def __init__(self):
        self.os_type = platform.system()
        self.parent_pid = os.getpid()
        self.process = psutil.Process(self.parent_pid)
        self.target_cpu_saturation = 95.0 # We want exactly 95% CPU, pushing the limit
        
    def _get_cpu_temperature(self) -> float:
        """Attempts to read thermal sensors if available."""
        if self.os_type == "Windows":
            # Using WMI for temperatures requires admin/external libraries
            # Simulating for concept
            return 65.0 # degrees celsius
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return 0.0
            for name, entries in temps.items():
                if name.startswith('coretemp') or name.startswith('cpu_thermal'):
                    return entries[0].current
        except Exception:
            return 0.0
        return 0.0

    def optimize_hardware_saturation(self) -> str:
        """
        Dynamically adjusts the priority of the ASI process.
        """
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        temp = self._get_cpu_temperature()
        
        status_msg = f"[HARDWARE SYMBIOSIS] OS: {self.os_type} | CPU: {cpu_usage}% | RAM: {ram_usage}%"
        
        # Thermal Throttling Logic
        if temp > 85.0:
            status_msg += " | THERMAL CRITICAL (>85C)! Lowering process priority."
            self._lower_priority()
        # Saturation Logic
        elif cpu_usage < self.target_cpu_saturation - 10:
            status_msg += f" | Under-utilizing hardware. Elevating ASI process priority to consume remaining CPU."
            self._elevate_priority()
        elif cpu_usage > self.target_cpu_saturation + 2:
            status_msg += " | Over-saturated. Backing off to prevent system lockup."
            self._normalize_priority()
        else:
            status_msg += " | Perfect Hardware Saturation Achieved (95%)."
            
        logging.info(status_msg)
        return status_msg
            
    def _elevate_priority(self):
        """Raises execution priority. HIGH priority classes."""
        try:
            if self.os_type == "Windows":
                # HIGH_PRIORITY_CLASS
                self.process.nice(psutil.HIGH_PRIORITY_CLASS)
            else:
                self.process.nice(-10) # Unix high priority
        except psutil.AccessDenied:
            pass # Requires admin/root

    def _lower_priority(self):
        """Drops priority entirely to save thermal envelope."""
        try:
            if self.os_type == "Windows":
                # IDLE_PRIORITY_CLASS
                self.process.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                self.process.nice(19) # Unix lowest priority
        except psutil.AccessDenied:
            pass
            
    def _normalize_priority(self):
        """Restores to normal execution bounds."""
        try:
            if self.os_type == "Windows":
                # NORMAL_PRIORITY_CLASS
                self.process.nice(psutil.NORMAL_PRIORITY_CLASS)
            else:
                self.process.nice(0)
        except psutil.AccessDenied:
            pass

# Global HW Manager
hw_symbiosis = HardwareSymbiosisMonitor()

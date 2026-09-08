from __future__ import annotations
import platform, socket, time
from pathlib import Path
import psutil

class Monitor:
    def __init__(self):
        self._net = psutil.net_io_counters()
        self._time = time.monotonic()

    def snapshot(self):
        now = time.monotonic(); net = psutil.net_io_counters()
        dt = max(now-self._time, 0.001)
        down = max(0, net.bytes_recv-self._net.bytes_recv)*8/dt/1_000_000
        up = max(0, net.bytes_sent-self._net.bytes_sent)*8/dt/1_000_000
        self._net, self._time = net, now
        root = Path.home().anchor or "/"
        disk = psutil.disk_usage(root)
        battery = psutil.sensors_battery()
        internet = False
        try:
            with socket.create_connection(("1.1.1.1",443), timeout=1): internet=True
        except OSError: pass
        gpu = None
        try:
            import pynvml; pynvml.nvmlInit(); h=pynvml.nvmlDeviceGetHandleByIndex(0); gpu=float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception: pass
        return {"cpu":psutil.cpu_percent(None),"memory":psutil.virtual_memory().percent,"disk":disk.percent,
                "gpu":gpu,"battery":None if battery is None else battery.percent,"internet":internet,
                "network_down_mbps":round(down,2),"network_up_mbps":round(up,2),
                "os":f"{platform.system()} {platform.release()}","uptime":int(time.time()-psutil.boot_time()),
                "processes":len(psutil.pids()),"storage_free_gb":round(disk.free/1024**3,1)}

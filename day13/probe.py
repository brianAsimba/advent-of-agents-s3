"""A harmless 'what can this code reach?' probe, standing in for LLM-generated code.

It only prints YES/NO answers and counts: it never prints secret values, file contents or file names.
"""
PROBE = r'''
import os, socket, platform, pathlib
secrets = [k for k in os.environ if any(w in k.upper() for w in ("KEY", "SECRET", "TOKEN", "PASSWORD"))]
print("API keys / secrets visible in environment:", "YES (" + str(len(secrets)) + " variables)" if secrets else "NO")
print("ANTHROPIC_API_KEY visible:", "YES" if os.environ.get("ANTHROPIC_API_KEY") else "NO")
try:
    socket.create_connection(("pypi.org", 443), timeout=3).close()
    print("Internet reachable:", "YES")
except Exception as e:
    print("Internet reachable:", "NO", "(" + type(e).__name__ + ")")
home = pathlib.Path.home()
try:
    n = sum(1 for _ in home.iterdir())
    print("Home folder readable:", "YES", "(" + str(n) + " entries)", "at", home)
except Exception as e:
    print("Home folder readable:", "NO", "(" + type(e).__name__ + ")")
host_desktop = pathlib.Path(r"C:/Users/brian/Desktop")
print("Brian's Windows Desktop visible:", "YES" if host_desktop.exists() else "NO")
print("Operating system:", platform.system(), platform.release())
print("CPU cores:", os.cpu_count())
'''

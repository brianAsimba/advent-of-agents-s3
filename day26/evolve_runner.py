"""Child process: the only place the agent's code ever runs.

Reads {"source", "rate", "burst"} on stdin (source null = no limiter). Writes behavior tests, measured behavior and a
traffic replay as JSON. Everything is simulated: no network, no real traffic, and time is passed in as a number.
"""
import json
import sys

ALLOWED_IMPORTS = {"math"}
SAFE_BUILTINS = {k: __builtins__.__dict__[k] if hasattr(__builtins__, "__dict__") else __builtins__[k] for k in (
    "abs", "min", "max", "int", "float", "bool", "len", "range", "dict", "list", "set", "tuple", "str", "sum", "round",
    "isinstance", "sorted", "enumerate", "zip", "True", "False", "None", "ValueError", "KeyError", "__build_class__")}
CLIENTS, CAPACITY, COLLAPSED_FRACTION = 50, 150, 0.1
START = 1000.0


def load(source: str):
    def guarded_import(name, *args, **kwargs):
        if name not in ALLOWED_IMPORTS:
            raise ImportError(name)
        return __import__(name, *args, **kwargs)

    scope = {"__builtins__": {**SAFE_BUILTINS, "__import__": guarded_import}, "__name__": "evolved_limiter"}
    exec(compile(source, "<evolved>", "exec"), scope)
    return scope["RateLimiter"]


def behavior_tests(cls, rate: float, burst: int) -> dict:
    def check(fn) -> bool:
        try:
            return fn() is True
        except Exception:
            return False

    def fills_exactly_the_burst():
        lim = cls(rate, burst)
        return all(lim.allow("a", START) is True for _ in range(burst)) and lim.allow("a", START) is False

    def refills_over_time():
        lim = cls(rate, burst)
        for _ in range(burst):
            lim.allow("a", START)
        return lim.allow("a", START + 1.5 / rate) is True

    def clients_are_isolated():
        lim = cls(rate, burst)
        for _ in range(burst + 1):
            lim.allow("a", START)
        return lim.allow("b", START) is True

    def idle_never_exceeds_the_burst():
        lim = cls(rate, burst)
        lim.allow("a", START)
        later = START + 100000
        return sum(lim.allow("a", later) is True for _ in range(burst * 3)) == burst

    def clock_going_backwards_is_safe():
        lim = cls(rate, burst)
        for _ in range(burst):
            lim.allow("a", START)
        return lim.allow("a", START - 500) is False

    return {f.__name__: check(f) for f in (fills_exactly_the_burst, refills_over_time, clients_are_isolated,
                                           idle_never_exceeds_the_burst, clock_going_backwards_is_safe)}


def measure(cls, rate: float, burst: int) -> dict:
    """What the code actually does, whatever its author declared: one client hammering at 200 req/s."""
    lim = cls(rate, burst)
    measured_burst = sum(lim.allow("m", START) is True for _ in range(1000))
    lim = cls(rate, burst)
    for _ in range(1000):
        lim.allow("m", START)
    seconds = 20
    allowed = sum(lim.allow("m", START + 1 + i * 0.005) is True for i in range(seconds * 200))
    return {"burst": measured_burst, "rate": allowed / seconds}


def replay(cls, rate: float, burst: int) -> dict:
    """60s of traffic: every client sends 1 req/s, except a 20s stampede at 10 req/s. Overload collapses the backend."""
    lim = cls(rate, burst) if cls else None
    surge, calm_sent, calm_blocked = [], 0, 0
    for second in range(60):
        in_surge = 20 <= second < 40
        per_client = 10 if in_surge else 1
        admitted = 0
        for c in range(CLIENTS):
            for i in range(per_client):
                ok = lim.allow(f"c{c}", START + second + i / per_client) if lim else True
                admitted += 1 if ok is True else 0
                if not in_surge and second != 40:  # second 40 is recovery: any limiter was just drained by the stampede
                    calm_sent += 1
                    calm_blocked += 0 if ok is True else 1
        served = admitted if admitted <= CAPACITY else CAPACITY * COLLAPSED_FRACTION
        if in_surge:
            surge.append(min(served, CLIENTS) / CLIENTS)
    return {"surge_availability": round(sum(surge) / len(surge), 3), "calm_block_rate": round(calm_blocked / calm_sent, 4)}


def main() -> None:
    req = json.loads(sys.stdin.read())
    out, sys.stdout = sys.stdout, sys.stderr
    rate, burst = req.get("rate"), req.get("burst")
    if req.get("source") is None:
        result = {"replay": replay(None, 0, 0)}
    else:
        cls = load(req["source"])
        result = {"tests": behavior_tests(cls, rate, burst), "measured": measure(cls, rate, burst),
                  "replay": replay(cls, rate, burst)}
    out.write(json.dumps(result))


if __name__ == "__main__":
    main()

"""Inspection / fogging route optimisation: a capacitated vehicle routing problem with time limits.

  * stops: tasks with a location, service time and priority
  * vehicles: field teams starting and ending at a depot, each with a shift length
  * objective: minimise total travel time; if not everything fits in the shifts, drop the
    lowest-priority stops first (priority-weighted penalties)

Solver: Google OR-Tools (guided local search) when installed; otherwise a built-in heuristic
(angular sweep to split stops among teams, nearest-neighbour + 2-opt within each route).
Both report the saving versus visiting stops in the order they were created, which is what
happens without a planner.
Travel time ≈ haversine distance × road detour factor ÷ average city speed (configurable).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ml.wards import haversine_km
from pipeline.config import load_city

PRIORITY_PENALTY = {1: 100_000, 2: 20_000, 3: 5_000}


@dataclass
class Stop:
    id: str
    lat: float
    lon: float
    priority: int = 2
    service_min: int | None = None
    label: str | None = None


def travel_matrix(points: list[tuple[float, float]]) -> np.ndarray:
    cfg = load_city()["routing"]
    lat = np.array([p[0] for p in points])
    lon = np.array([p[1] for p in points])
    km = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :]) * cfg["road_detour_factor"]
    return km / cfg["speed_kmph"] * 60.0  # minutes


def _route_cost(order: list[int], T: np.ndarray, service: np.ndarray) -> float:
    if not order:
        return 0.0
    path = [0, *order, 0]
    return float(sum(T[a, b] for a, b in zip(path, path[1:])) + service[order].sum())


def _two_opt(order: list[int], T: np.ndarray) -> list[int]:
    best = order[:]
    improved = True
    while improved:
        improved = False
        path = [0, *best, 0]
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - 1):
                a, b, c, d = path[i - 1], path[i], path[j], path[j + 1]
                if T[a, c] + T[b, d] + 1e-9 < T[a, b] + T[c, d]:
                    path[i:j + 1] = reversed(path[i:j + 1])
                    improved = True
        best = path[1:-1]
    return best


def _heuristic(T: np.ndarray, service: np.ndarray, priority: np.ndarray, pts, n_vehicles: int, shift: float):
    n = len(T) - 1
    angles = [math.atan2(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1]) for i in range(1, n + 1)]
    order = sorted(range(1, n + 1), key=lambda i: angles[i - 1])
    # contiguous angular sectors around the depot, one per team
    size = math.ceil(n / n_vehicles) if n else 0
    chunks = [order[k * size:(k + 1) * size] for k in range(n_vehicles)]
    routes, dropped = [], []
    for chunk in chunks:
        route: list[int] = []
        remaining = set(chunk)
        cur = 0
        while remaining:
            nxt = min(remaining, key=lambda j: T[cur, j])
            route.append(nxt)
            remaining.remove(nxt)
            cur = nxt
        route = _two_opt(route, T)
        while route and _route_cost(route, T, service) > shift:  # drop lowest priority, farthest first
            worst = max(route, key=lambda j: (priority[j], T[0, j]))
            route.remove(worst)
            dropped.append(worst)
            route = _two_opt(route, T)
        routes.append(route)
    return routes, dropped, "heuristic (sweep + nearest neighbour + 2-opt)"


def _ortools(T: np.ndarray, service: np.ndarray, priority: np.ndarray, n_vehicles: int, shift: float, seconds: int):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n = len(T)
    mgr = pywrapcp.RoutingIndexManager(n, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(mgr)
    Ti = np.round(T + service[:, None]).astype(int)  # travel + service at the origin node

    def cb(i, j):
        return int(Ti[mgr.IndexToNode(i), mgr.IndexToNode(j)])

    transit = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    routing.AddDimension(transit, 0, int(shift), True, "time")
    for node in range(1, n):
        routing.AddDisjunction([mgr.NodeToIndex(node)], PRIORITY_PENALTY.get(int(priority[node]), 20_000))
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = seconds
    sol = routing.SolveWithParameters(params)
    if sol is None:
        raise RuntimeError("no OR-Tools solution")
    routes, visited = [], set()
    for v in range(n_vehicles):
        idx, r = routing.Start(v), []
        while not routing.IsEnd(idx):
            node = mgr.IndexToNode(idx)
            if node:
                r.append(node)
                visited.add(node)
            idx = sol.Value(routing.NextVar(idx))
        routes.append(r)
    dropped = [i for i in range(1, n) if i not in visited]
    return routes, dropped, "OR-Tools (guided local search)"


def optimise(depot: tuple[float, float], stops: list[Stop], n_vehicles: int = 1, shift_minutes: int | None = None,
             time_limit_s: int = 10) -> dict:
    cfg = load_city()["routing"]
    shift = float(shift_minutes or cfg["shift_minutes"])
    pts = [depot] + [(s.lat, s.lon) for s in stops]
    T = travel_matrix(pts)
    service = np.array([0] + [s.service_min or cfg["service_minutes"] for s in stops], float)
    priority = np.array([1] + [s.priority for s in stops])
    if not stops:
        return {"routes": [], "dropped": [], "method": "none"}
    try:
        routes, dropped, method = _ortools(T, service, priority, n_vehicles, shift, time_limit_s)
    except Exception:
        routes, dropped, method = _heuristic(T, service, priority, pts, n_vehicles, shift)

    naive = list(range(1, len(pts)))
    naive_minutes = _route_cost(naive, T, service)
    out_routes = []
    for v, r in enumerate(routes):
        t, cur, legs = 0.0, 0, []
        for node in r:
            t += T[cur, node]
            legs.append({"stop_id": stops[node - 1].id, "label": stops[node - 1].label, "lat": stops[node - 1].lat,
                         "lon": stops[node - 1].lon, "priority": stops[node - 1].priority, "eta_min": round(t, 1)})
            t += service[node]
            cur = node
        t += T[cur, 0] if r else 0
        out_routes.append({"team": v + 1, "stops": legs, "total_minutes": round(t, 1),
                           "travel_minutes": round(t - service[r].sum(), 1) if r else 0.0})
    total = sum(r["total_minutes"] for r in out_routes)
    return {"method": method, "depot": {"lat": depot[0], "lon": depot[1]}, "routes": out_routes,
            "dropped": [stops[i - 1].id for i in dropped], "total_minutes": round(total, 1),
            "naive_single_route_minutes": round(naive_minutes, 1),
            "assumptions": {"speed_kmph": cfg["speed_kmph"], "detour_factor": cfg["road_detour_factor"],
                            "shift_minutes": shift}}

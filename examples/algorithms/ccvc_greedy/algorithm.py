from __future__ import annotations

import hashlib
import ipaddress
import random
import subprocess
import time
from typing import Dict, List, Optional, Set, Tuple

from caduceus_sdk.node_base import Node


class Color:
    WHITE = "WHITE"
    GRAY = "GRAY"
    BLACK = "BLACK"
    RED = "RED"


def _overlay_from_color(color: str) -> dict:
    c = (color or "").strip().upper()
    if c == Color.BLACK:
        return {"fill": "#000000", "text": "#ffffff", "border": "#111827", "badge": "BLACK"}
    if c == Color.GRAY:
        return {"fill": "#9ca3af", "text": "#111827", "border": "#374151", "badge": "GRAY"}
    if c == Color.RED:
        return {"fill": "#ef4444", "text": "#ffffff", "border": "#7f1d1d", "badge": "RED"}
    return {"fill": "#ffffff", "text": "#111827", "border": "#111827", "badge": "WHITE"}


def _stable_priority(seed: int, tag: str, node_id: int) -> float:
    """
    Deterministic tie-break helper.
    """
    msg = f"{int(seed)}:{tag}:{int(node_id)}".encode("utf-8", errors="ignore")
    digest = hashlib.blake2b(msg, digest_size=8).digest()
    v = int.from_bytes(digest, byteorder="big", signed=False)
    return float(v) / float(2**64)


def _bfs_components(adj: Dict[int, Set[int]], nodes: Set[int]) -> List[Set[int]]:
    if not nodes:
        return []
    visited: Set[int] = set()
    comps: List[Set[int]] = []
    for start in sorted(nodes):
        if start in visited:
            continue
        q = [start]
        comp: Set[int] = set()
        while q:
            u = q.pop(0)
            if u in visited:
                continue
            visited.add(u)
            comp.add(u)
            for v in adj.get(u, set()):
                if v in nodes and v not in visited:
                    q.append(v)
        comps.append(comp)
    return comps


def greedy_capacitated_connected_vertex_cover(
    *,
    adj: Dict[int, Set[int]],
    weights: Dict[int, float],
    k: int,
    seed: int = 1,
    max_history_steps: int = 200,
) -> Tuple[Set[int], bool, List[dict]]:
    """
    Greedy Capacitated Connected Vertex Cover (CCVC) inspired by the user-provided pseudocode.

    - Each selected vertex (BLACK) can cover at most k incident uncovered edges.
    - Prefer selecting RED nodes first, then WHITE, then GRAY (with remaining capacity).
    - After selecting a BLACK node, cover up to remaining capacity edges, prioritizing WHITE neighbors.
    - If the resulting cover set is disconnected, try to connect components by adding low-cost bridge vertices.

    Returns: (final_cover_set, is_connected, history)
    """
    k = int(max(0, k))
    rng = random.Random(int(seed))

    # Normalize adjacency to ensure undirected symmetry and include all nodes.
    all_nodes: Set[int] = set(int(x) for x in adj.keys())
    for u, nbs in list(adj.items()):
        uu = int(u)
        all_nodes.add(uu)
        adj.setdefault(uu, set())
        for v in list(nbs or set()):
            vv = int(v)
            if vv == uu:
                continue
            all_nodes.add(vv)
            adj.setdefault(vv, set()).add(uu)
            adj[uu].add(vv)

    # Undirected edge set
    edges: Set[Tuple[int, int]] = set()
    for u, nbs in adj.items():
        for v in nbs:
            if u == v:
                continue
            a, b = (u, v) if u < v else (v, u)
            edges.add((int(a), int(b)))

    if not edges:
        history = [
            {
                "type": "connectivity",
                "original_cover": [],
                "components_found": 0,
                "bridges_added": [],
                "final_cover": [],
                "final_connected": True,
                "k": int(k),
            }
        ]
        return set(), True, history

    uncovered_edges: Set[Tuple[int, int]] = set(edges)  # edges not yet assigned to any selected vertex
    cover_set: Set[int] = set()
    used_by_count: Dict[int, int] = {nid: 0 for nid in all_nodes}
    assigned_edge_to: Dict[Tuple[int, int], int] = {}  # (a,b) -> vertex_id in cover_set

    def _w(nid: int) -> float:
        try:
            return float(weights.get(int(nid), 1.0))
        except Exception:
            return 1.0

    def remaining_capacity(nid: int) -> int:
        return max(0, int(k) - int(used_by_count.get(int(nid), 0)))

    def uncovered_degree(nid: int) -> int:
        nid = int(nid)
        deg = 0
        for nb in adj.get(nid, set()):
            a, b = (nid, nb) if nid < nb else (nb, nid)
            if (a, b) in uncovered_edges:
                deg += 1
        return deg

    # Base coloring derived from current assignment:
    #   BLACK = selected (in cover_set)
    #   WHITE = unselected and still incident to uncovered edges
    #   GRAY  = unselected and all incident edges are already assigned (covered by others)
    color: Dict[int, str] = {nid: Color.WHITE for nid in all_nodes}

    def _refresh_base_colors() -> None:
        for nid in all_nodes:
            if nid in cover_set:
                color[nid] = Color.BLACK
                continue
            color[nid] = Color.WHITE if uncovered_degree(nid) > 0 else Color.GRAY

    def is_white_leaf_of_black(nid: int) -> bool:
        nid = int(nid)
        if color.get(nid) != Color.WHITE:
            return False
        nbs = sorted(adj.get(nid, set()))
        if len(nbs) != 1:
            return False
        nb = int(nbs[0])
        if nb not in cover_set:
            return False
        a, b = (nid, nb) if nid < nb else (nb, nid)
        return (a, b) in uncovered_edges

    def has_white_leaf_neighbor(nid: int) -> bool:
        nid = int(nid)
        if color.get(nid) != Color.WHITE:
            return False
        for nb in adj.get(nid, set()):
            nb = int(nb)
            if color.get(nb) != Color.WHITE:
                continue
            if len(adj.get(nb, set())) != 1:
                continue
            a, b = (nid, nb) if nid < nb else (nb, nid)
            if (a, b) in uncovered_edges:
                return True
        return False

    def _best_of(node_ids: List[int], tag: str) -> Optional[int]:
        if not node_ids:
            return None
        info = [(uncovered_degree(n), _w(n), int(n)) for n in node_ids]
        rng.shuffle(info)
        info.sort(key=lambda x: (-x[0], x[1], _stable_priority(seed, tag, x[2])))
        return int(info[0][2])

    def mark_isolated_white_leaves_as_red() -> List[int]:
        red_marked: List[int] = []
        for nid in sorted(all_nodes):
            if is_white_leaf_of_black(nid):
                color[nid] = Color.RED
                red_marked.append(int(nid))
        return red_marked

    def mark_one_hop_away_as_red() -> List[int]:
        red_marked: List[int] = []
        for nid in sorted(all_nodes):
            if color.get(nid) != Color.WHITE:
                continue
            if has_white_leaf_neighbor(nid):
                color[nid] = Color.RED
                red_marked.append(int(nid))
        return red_marked

    def pick_next_node() -> Tuple[Optional[int], Optional[str]]:
        red = [n for n in all_nodes if color.get(n) == Color.RED]
        if red:
            return _best_of(red, "RED"), Color.RED

        white = [n for n in all_nodes if color.get(n) == Color.WHITE]
        if white:
            return _best_of(white, "WHITE"), Color.WHITE

        return None, None

    class _Dinic:
        __slots__ = ("n", "g", "level", "it")

        class _E:
            __slots__ = ("to", "rev", "cap")

            def __init__(self, to: int, rev: int, cap: int):
                self.to = to
                self.rev = rev
                self.cap = cap

        def __init__(self, n: int):
            self.n = n
            self.g: List[List[_Dinic._E]] = [[] for _ in range(n)]
            self.level: List[int] = [0] * n
            self.it: List[int] = [0] * n

        def add_edge(self, fr: int, to: int, cap: int) -> None:
            cap = int(cap)
            fwd = _Dinic._E(to, len(self.g[to]), cap)
            rev = _Dinic._E(fr, len(self.g[fr]), 0)
            self.g[fr].append(fwd)
            self.g[to].append(rev)

        def bfs(self, s: int, t: int) -> bool:
            from collections import deque

            self.level = [-1] * self.n
            q = deque([s])
            self.level[s] = 0
            while q:
                v = q.popleft()
                for e in self.g[v]:
                    if e.cap <= 0:
                        continue
                    if self.level[e.to] != -1:
                        continue
                    self.level[e.to] = self.level[v] + 1
                    q.append(e.to)
            return self.level[t] != -1

        def dfs(self, v: int, t: int, f: int) -> int:
            if v == t:
                return f
            for i in range(self.it[v], len(self.g[v])):
                self.it[v] = i
                e = self.g[v][i]
                if e.cap <= 0:
                    continue
                if self.level[e.to] != self.level[v] + 1:
                    continue
                ret = self.dfs(e.to, t, min(f, e.cap))
                if ret <= 0:
                    continue
                e.cap -= ret
                self.g[e.to][e.rev].cap += ret
                return ret
            return 0

        def max_flow(self, s: int, t: int) -> int:
            flow = 0
            INF = 10**9
            while self.bfs(s, t):
                self.it = [0] * self.n
                while True:
                    f = self.dfs(s, t, INF)
                    if f <= 0:
                        break
                    flow += f
            return flow

    def _recompute_assignment() -> None:
        nonlocal uncovered_edges, assigned_edge_to, used_by_count
        uncovered_edges = set(edges)
        assigned_edge_to = {}
        used_by_count = {nid: 0 for nid in all_nodes}

        if not cover_set or k <= 0:
            _refresh_base_colors()
            return

        edge_list = sorted(edges)
        cover_nodes = sorted(int(x) for x in cover_set)
        v_index: Dict[int, int] = {nid: i for i, nid in enumerate(cover_nodes)}

        # Nodes: source + edge_nodes + vertex_nodes + sink
        src = 0
        edge_offset = 1
        vert_offset = edge_offset + len(edge_list)
        sink = vert_offset + len(cover_nodes)
        dinic = _Dinic(sink + 1)

        # Keep handles for src->edge arcs to detect assignment.
        src_edge_handles: List[_Dinic._E] = []
        edge_to_vertices: List[Tuple[int, int, List[int]]] = []  # (a,b,[vertexNodeIdx...])

        for i, (a, b) in enumerate(edge_list):
            enode = edge_offset + i
            dinic.add_edge(src, enode, 1)
            src_edge_handles.append(dinic.g[src][-1])
            candidates: List[int] = []
            if a in v_index:
                vnode = vert_offset + v_index[a]
                dinic.add_edge(enode, vnode, 1)
                candidates.append(vnode)
            if b in v_index:
                vnode = vert_offset + v_index[b]
                dinic.add_edge(enode, vnode, 1)
                candidates.append(vnode)
            edge_to_vertices.append((int(a), int(b), candidates))

        for nid, idx in v_index.items():
            vnode = vert_offset + idx
            dinic.add_edge(vnode, sink, int(k))

        dinic.max_flow(src, sink)

        # Extract assignment from residual graph:
        for i, (a, b, _cands) in enumerate(edge_to_vertices):
            enode = edge_offset + i
            # If src->edge has cap==0 then this edge is assigned.
            if src_edge_handles[i].cap != 0:
                continue
            assigned_vertex: Optional[int] = None
            for e in dinic.g[enode]:
                # Forward edges to vertex nodes that are fully used (cap==0) indicate assignment.
                if e.to < vert_offset or e.to >= sink:
                    continue
                if e.cap == 0:
                    idx = int(e.to - vert_offset)
                    if 0 <= idx < len(cover_nodes):
                        assigned_vertex = int(cover_nodes[idx])
                        break
            if assigned_vertex is None:
                continue
            edge = (int(a), int(b))
            assigned_edge_to[edge] = assigned_vertex
            uncovered_edges.discard(edge)
            used_by_count[assigned_vertex] = int(used_by_count.get(assigned_vertex, 0)) + 1

        _refresh_base_colors()

    def pick_repair_node() -> Optional[int]:
        if not uncovered_edges:
            return None
        if not cover_set:
            # Pick an endpoint of any uncovered edge
            a, b = next(iter(uncovered_edges))
            return int(a)

        # Focus on saturated vertices that are endpoints of uncovered edges.
        saturated: Set[int] = set()
        for a, b in uncovered_edges:
            if a in cover_set and remaining_capacity(a) <= 0:
                saturated.add(int(a))
            if b in cover_set and remaining_capacity(b) <= 0:
                saturated.add(int(b))

        candidates = [n for n in all_nodes if n not in cover_set]
        if not candidates:
            return None

        def relief_score(nid: int) -> int:
            # Count how many currently-assigned edges (nid, sat) are assigned to sat; selecting nid could reassign them.
            score = 0
            for nb in adj.get(int(nid), set()):
                nb = int(nb)
                if nb not in saturated:
                    continue
                a, b = (nid, nb) if nid < nb else (nb, nid)
                if assigned_edge_to.get((a, b)) == nb:
                    score += 1
            return score

        scored: List[Tuple[int, int, float, int]] = []
        for nid in candidates:
            rel = relief_score(int(nid))
            deg = uncovered_degree(int(nid))
            scored.append((rel, deg, -_w(int(nid)), int(nid)))
        rng.shuffle(scored)
        scored.sort(key=lambda x: (-x[0], -x[1], x[2], _stable_priority(seed, "REPAIR", x[3])))

        best_rel, best_deg, _nw, best = scored[0]
        if best_rel <= 0 and best_deg <= 0:
            return None
        return int(best)

    history: List[dict] = []
    iteration = 0
    max_iterations = int(max(10, len(all_nodes) * 5))

    _recompute_assignment()

    while uncovered_edges and iteration < max_iterations:
        new_red_from_leaves = mark_isolated_white_leaves_as_red()
        new_red_from_one_hop = mark_one_hop_away_as_red()

        nid, node_type = pick_next_node()
        if nid is None:
            nid = pick_repair_node()
            node_type = "REPAIR"

        if nid is None:
            history.append(
                {
                    "type": "stalled",
                    "remaining_uncovered_edges": int(len(uncovered_edges)),
                    "k": int(k),
                    "selected": int(len(cover_set)),
                    "edges": int(len(edges)),
                    "example_edges": [{"a": int(a), "b": int(b)} for (a, b) in list(sorted(uncovered_edges))[:10]],
                }
            )
            break

        cover_set.add(int(nid))
        _recompute_assignment()

        if len(history) < max_history_steps:
            history.append(
                {
                    "type": "iteration",
                    "iteration": int(iteration),
                    "selected_black": int(nid),
                    "node_type": node_type,
                    "edges_assigned_total": int(len(edges) - len(uncovered_edges)),
                    "remaining_uncovered_edges": int(len(uncovered_edges)),
                    "new_red_from_leaves": [int(x) for x in new_red_from_leaves],
                    "new_red_from_one_hop": [int(x) for x in new_red_from_one_hop],
                    "selected_used": int(used_by_count.get(int(nid), 0)),
                }
            )

        iteration += 1

    # Connectivity check + bridges (capacity-aware, like your code)
    comps = _bfs_components(adj, set(cover_set))
    is_connected = len(comps) <= 1
    bridges_added: Set[int] = set()
    initial_cover = set(cover_set)

    def shortest_feasible_path(
        start_ids: List[int],
        target_ids: Set[int],
        live_cover: Set[int],
    ) -> Tuple[float, List[int]]:
        import heapq

        pq: List[Tuple[float, int, List[int]]] = []
        best: Dict[int, float] = {}
        targets = set(target_ids)

        for src in start_ids:
            pq.append((0.0, src, [src]))
            best[src] = 0.0
        heapq.heapify(pq)

        while pq:
            cost, nid, path = heapq.heappop(pq)
            if nid in targets:
                return cost, path
            if best.get(nid, float("inf")) < cost:
                continue

            for nb in adj.get(nid, set()):
                step_cost = 0.0
                if nb not in live_cover:
                    step_cost = float(weights.get(nb, 1.0))
                new_cost = cost + step_cost
                if new_cost < best.get(nb, float("inf")):
                    best[nb] = new_cost
                    heapq.heappush(pq, (new_cost, nb, path + [nb]))

        return float("inf"), []

    def build_bridges_capacity_aware(live_cover: Set[int]) -> Set[int]:
        local_comps = _bfs_components(adj, set(live_cover))
        if len(local_comps) <= 1:
            return set()

        cheapest: Dict[Tuple[int, int], Tuple[float, List[int]]] = {}
        for i, comp_a in enumerate(local_comps):
            for j in range(i + 1, len(local_comps)):
                comp_b = local_comps[j]
                cost, path = shortest_feasible_path(sorted(comp_a), set(comp_b), live_cover)
                if path:
                    cheapest[(i, j)] = (cost, path)

        parent = list(range(len(local_comps)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        bridges: Set[int] = set()
        for (i, j), (cost, path) in sorted(cheapest.items(), key=lambda x: x[1][0]):
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            parent[ri] = rj
            for nid in path[1:-1]:
                if nid not in live_cover:
                    bridges.add(nid)
                    live_cover.add(nid)

        roots = {find(r) for r in range(len(local_comps))}
        if len(roots) > 1:
            return set()
        return bridges

    if not is_connected and cover_set:
        bridges_added = build_bridges_capacity_aware(set(cover_set))
        cover_set = set(cover_set) | set(bridges_added)
        is_connected = len(_bfs_components(adj, set(cover_set))) <= 1
        _recompute_assignment()

    history.append(
        {
            "type": "connectivity",
            "original_cover": sorted({int(x) for x in initial_cover}),
            "components_found": int(len(comps)),
            "bridges_added": sorted({int(x) for x in bridges_added}),
            "final_cover": sorted({int(x) for x in cover_set}),
            "final_connected": bool(is_connected),
            "k": int(k),
            "assigned_edges": int(len(edges) - len(uncovered_edges)),
            "unassigned_edges": int(len(uncovered_edges)),
        }
    )

    return set(cover_set), bool(is_connected), history


class CCVCNode(Node):
    """
    Example algorithm: Greedy Capacitated Connected Vertex Cover (CCVC).

    Runs in-emulation using only neighbor-to-neighbor messaging (no global IP routing needed):
      1) Neighbor discovery via broadcast/multicast HELLO
      2) Leader election (min node id) via gossip
      3) BFS tree rooted at leader
      4) Leader gathers global adjacency up the tree
      5) Leader runs greedy CCVC and broadcasts final cover membership down the tree
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self.color = Color.WHITE
        self.weight = float(self.G.nodes[self.id].get("weight", 1.0) or 1.0)

        self.neighbors: Dict[int, Tuple[str, int]] = {}  # neighbor_id -> (ip, port)
        self._local_ipv4_networks: list[ipaddress.IPv4Network] = []
        self._local_ipv4_cidrs: list[str] = []

        self.leader_id = int(self.id)
        self.parent: Optional[int] = None
        self.dist: int = 1_000_000_000

        self._leader_seen: Set[int] = set()
        self._info_seen: Set[int] = set()
        self._flood_seen: Set[str] = set()

    def _load_local_ipv4(self) -> None:
        if self._local_ipv4_networks:
            return
        try:
            out = subprocess.check_output(
                ["sh", "-lc", "ip -4 -o addr show up 2>/dev/null || true"],
                stderr=subprocess.DEVNULL,
                timeout=0.5,
            ).decode("utf-8", errors="replace")
        except Exception:
            out = ""
        nets: list[ipaddress.IPv4Network] = []
        cidrs: list[str] = []
        for line in out.splitlines():
            parts = line.strip().split()
            if "inet" not in parts:
                continue
            try:
                inet_idx = parts.index("inet")
                cidr = str(parts[inet_idx + 1] or "").strip()
            except Exception:
                continue
            if not cidr or "/" not in cidr:
                continue
            try:
                iface = ipaddress.ip_interface(cidr)
                if iface.ip.is_loopback:
                    continue
                nets.append(iface.network)
                cidrs.append(cidr)
            except Exception:
                continue
        nets.sort(key=lambda n: int(getattr(n, "prefixlen", 0)), reverse=True)
        self._local_ipv4_networks = nets
        self._local_ipv4_cidrs = cidrs[:16]

    def _pick_reachable_ip(self, candidate_cidrs: list[str], fallback_ip: str) -> str:
        self._load_local_ipv4()
        best_ip = ""
        best_score = -1
        for cidr in candidate_cidrs[:32]:
            ip_s = str(cidr or "").split("/", 1)[0].strip()
            if not ip_s:
                continue
            try:
                ip = ipaddress.ip_address(ip_s)
                if ip.version != 4:
                    continue
            except Exception:
                continue
            score = -1
            for net in self._local_ipv4_networks:
                try:
                    if ip in net:
                        score = max(score, int(net.prefixlen))
                        break
                except Exception:
                    continue
            if score > best_score:
                best_score = score
                best_ip = ip_s
        return best_ip or str(fallback_ip or "").strip()

    def _set_color(self, color: str) -> None:
        c = (color or "").strip().upper()
        if c not in (Color.WHITE, Color.GRAY, Color.BLACK, Color.RED):
            return
        if self.color == c:
            return
        self.color = c
        overlay = _overlay_from_color(self.color)
        self.write_state(
            {
                "ts": time.time(),
                "node": {"algo_id": self.id, "uuid": self.uuid, "name": self.name, "type": self.type},
                "color": self.color,
                "overlay": overlay,
            }
        )
        self.emit({"type": "overlay", "color": self.color, "overlay": overlay})

    def _drain_mailbox(self) -> list[dict]:
        out = []
        while True:
            msg = self.receiveMessage()
            if not msg:
                break
            out.append(msg)
        return out

    def _send_to_neighbor(self, neighbor_id: int, payload: dict) -> None:
        ip_port = self.neighbors.get(int(neighbor_id))
        if not ip_port:
            return
        ip, port = ip_port
        if not ip:
            return
        self.sendToAddr(ip, int(port), dict(payload))

    def _send_to_all_neighbors(self, payload: dict) -> None:
        for nid in list(self.neighbors.keys()):
            self._send_to_neighbor(int(nid), payload)

    def discover_neighbors(self) -> None:
        discovery_seconds = float(self.params.get("discovery_seconds", 3.0))
        hello_interval = float(self.params.get("hello_interval", 0.25))
        start = time.time()
        next_hello = 0.0
        self._load_local_ipv4()

        while time.time() - start < discovery_seconds:
            now = time.time()
            if now >= next_hello:
                self.broadcast({"type": "HELLO", "cidrs": list(self._local_ipv4_cidrs), "weight": self.weight})
                next_hello = now + hello_interval

            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                typ = str(msg.get("type") or "").upper()
                if typ not in ("HELLO", "HELLO_ACK"):
                    continue
                try:
                    sid = int(msg.get("sender"))
                except Exception:
                    continue
                if sid == self.id:
                    continue
                src_ip = str(msg.get("__src_ip") or "").strip()
                port = int(msg.get("__src_port") or self.ctx.listen_port)
                candidate_cidrs = msg.get("cidrs")
                if not isinstance(candidate_cidrs, list):
                    candidate_cidrs = []
                ip = self._pick_reachable_ip([str(x) for x in candidate_cidrs if x], fallback_ip=src_ip)
                if ip:
                    self.neighbors[int(sid)] = (ip, port)
                    if typ == "HELLO":
                        self.sendToAddr(ip, port, {"type": "HELLO_ACK", "cidrs": list(self._local_ipv4_cidrs), "weight": self.weight})

        self.emit({"type": "neighbors", "count": len(self.neighbors), "neighbors": sorted(self.neighbors.keys())})

    def elect_leader(self) -> None:
        election_seconds = float(self.params.get("election_seconds", 2.0))
        interval = float(self.params.get("election_interval", 0.25))
        start = time.time()
        next_send = 0.0
        last_change = time.time()
        stable_for = float(self.params.get("election_stable_for", 0.7))

        self.leader_id = int(self.id)
        while time.time() - start < election_seconds:
            now = time.time()
            if now >= next_send:
                self._send_to_all_neighbors({"type": "LEADER_CAND", "leader": int(self.leader_id)})
                next_send = now + interval

            yield self.mailbox.get(0.2)
            changed = False
            for msg in self._drain_mailbox():
                if str(msg.get("type") or "").upper() != "LEADER_CAND":
                    continue
                try:
                    cand = int(msg.get("leader"))
                except Exception:
                    continue
                if cand < int(self.leader_id):
                    self.leader_id = int(cand)
                    changed = True
            if changed:
                last_change = time.time()
            if time.time() - last_change >= stable_for:
                break

        self.emit({"type": "leader", "leader_id": int(self.leader_id)})

    def build_tree(self) -> None:
        tree_seconds = float(self.params.get("tree_seconds", 2.5))
        interval = float(self.params.get("tree_interval", 0.25))
        start = time.time()
        next_send = 0.0

        self.parent = None
        self.dist = 0 if int(self.id) == int(self.leader_id) else 1_000_000_000

        while time.time() - start < tree_seconds:
            now = time.time()
            if now >= next_send:
                if int(self.dist) < 1_000_000_000:
                    self._send_to_all_neighbors({"type": "TREE_ROOT", "leader": int(self.leader_id), "dist": int(self.dist)})
                next_send = now + interval

            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                typ = str(msg.get("type") or "").upper()
                if typ == "TREE_ROOT":
                    try:
                        leader = int(msg.get("leader"))
                        dist = int(msg.get("dist"))
                        sender = int(msg.get("sender"))
                    except Exception:
                        continue
                    if leader != int(self.leader_id):
                        continue
                    nd = dist + 1
                    if nd < int(self.dist):
                        self.dist = int(nd)
                        self.parent = int(sender)

        self.emit({"type": "tree", "leader_id": int(self.leader_id), "dist": int(self.dist), "parent": self.parent})

    def _handle_tree_forwarding(self, msg: dict) -> Optional[dict]:
        typ = str(msg.get("type") or "").upper()
        try:
            sender = int(msg.get("sender"))
        except Exception:
            sender = None

        # Flood (down/broadcast): forward once to all neighbors except the sender.
        if typ in ("REQ_INFO", "DECISION"):
            msg_id = str(msg.get("msg_id") or "").strip()
            if not msg_id:
                return msg
            key = f"{typ}:{msg_id}"
            if key in self._flood_seen:
                return msg
            self._flood_seen.add(key)
            for nb in sorted(self.neighbors.keys()):
                if sender is not None and int(nb) == int(sender):
                    continue
                self._send_to_neighbor(int(nb), msg)
            return msg

        # Up-tree forwarding
        if typ == "NODE_INFO":
            try:
                origin = int(msg.get("origin"))
            except Exception:
                origin = None
            if origin is not None:
                if int(self.id) == int(self.leader_id):
                    return msg
                if self.parent is not None:
                    self._send_to_neighbor(int(self.parent), msg)
            return None

        return msg

    def run(self):
        self._set_color(Color.WHITE)

        # 1) One-hop neighbor discovery
        yield from self.discover_neighbors()

        if not self.neighbors:
            # No links => trivial cover
            self._set_color(Color.BLACK)
            self.emit({"type": "done", "reason": "isolated_node"})
            return

        # 2) Leader election + BFS tree
        yield from self.elect_leader()
        yield from self.build_tree()

        # 3) Leader requests global node info
        k = int(self.params.get("k", 2))
        seed = int(self.params.get("seed", 1))

        if int(self.id) == int(self.leader_id):
            # Collect NODE_INFO from whole component
            nodes_info: Dict[int, dict] = {}
            nodes_info[int(self.id)] = {"weight": float(self.weight), "neighbors": sorted(self.neighbors.keys())}
            self._info_seen = {int(self.id)}

            self.emit({"type": "req_info", "k": int(k), "seed": int(seed)})
            msg_id = f"req:{int(time.time()*1000)}:{int(self.id)}"
            self._flood_seen.add(f"REQ_INFO:{msg_id}")
            req = {"type": "REQ_INFO", "msg_id": msg_id}
            for nb in sorted(self.neighbors.keys()):
                self._send_to_neighbor(int(nb), dict(req))

            gather_seconds = float(self.params.get("gather_seconds", 3.0))
            start = time.time()
            while time.time() - start < gather_seconds:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    msg = self._handle_tree_forwarding(msg) or {}
                    if not msg:
                        continue
                    if str(msg.get("type") or "").upper() != "NODE_INFO":
                        continue
                    try:
                        origin = int(msg.get("origin"))
                    except Exception:
                        continue
                    info = msg.get("info")
                    if not isinstance(info, dict):
                        continue
                    if origin in nodes_info:
                        continue
                    nodes_info[int(origin)] = info
                    self._info_seen.add(int(origin))

            # Build adjacency/weights (ensure symmetry)
            adj: Dict[int, Set[int]] = {}
            weights: Dict[int, float] = {}
            for nid, info in nodes_info.items():
                weights[int(nid)] = float(info.get("weight") or 1.0)
                nbs = info.get("neighbors") or []
                if not isinstance(nbs, list):
                    nbs = []
                adj.setdefault(int(nid), set()).update({int(x) for x in nbs if isinstance(x, (int, str)) and int(x) != int(nid)})
            for u, nbs in list(adj.items()):
                for v in list(nbs):
                    adj.setdefault(int(v), set()).add(int(u))

            cover, connected, history = greedy_capacitated_connected_vertex_cover(
                adj=adj,
                weights=weights,
                k=int(k),
                seed=int(seed),
                max_history_steps=int(self.params.get("max_history_steps", 200)),
            )
            cover = set(int(x) for x in cover)

            self.emit(
                {
                    "type": "result",
                    "nodes_seen": int(len(nodes_info)),
                    "edges": int(sum(len(v) for v in adj.values()) // 2),
                    "cover_size": int(len(cover)),
                    "connected": bool(connected),
                    "cover": sorted(cover)[:200],
                }
            )
            for item in history[:200]:
                self.emit({"type": "history", **item})

            decision_msg = {
                "type": "DECISION",
                "msg_id": f"dec:{int(time.time()*1000)}:{int(self.id)}",
                "cover": sorted(cover),
                "connected": bool(connected),
                "k": int(k),
            }
            self._flood_seen.add(f"DECISION:{decision_msg['msg_id']}")
            for nb in sorted(self.neighbors.keys()):
                self._send_to_neighbor(int(nb), dict(decision_msg))

            self._set_color(Color.BLACK if int(self.id) in cover else Color.GRAY)
            self.emit({"type": "done", "leader": True, "color": self.color})
            return

        # Non-leader: respond to REQ_INFO and wait for DECISION
        sent_info = False
        decided = False
        cover_set: Set[int] = set()

        timeout_s = float(self.params.get("decision_timeout", 12.0))
        start = time.time()
        while time.time() - start < timeout_s and not decided:
            yield self.mailbox.get(0.2)
            for raw in self._drain_mailbox():
                msg = self._handle_tree_forwarding(raw) or {}
                if not msg:
                    continue
                typ = str(msg.get("type") or "").upper()

                if typ == "REQ_INFO" and not sent_info:
                    info = {"weight": float(self.weight), "neighbors": sorted(self.neighbors.keys())}
                    up = {"type": "NODE_INFO", "origin": int(self.id), "info": info}
                    if self.parent is not None:
                        self._send_to_neighbor(int(self.parent), up)
                        sent_info = True
                        self.emit({"type": "sent_info", "to": int(self.parent)})

                if typ == "DECISION":
                    cov = msg.get("cover")
                    if isinstance(cov, list):
                        try:
                            cover_set = {int(x) for x in cov if isinstance(x, (int, str))}
                        except Exception:
                            cover_set = set()
                    decided = True
                    break

        if decided:
            self._set_color(Color.BLACK if int(self.id) in cover_set else Color.GRAY)
            self.emit({"type": "done", "leader": False, "color": self.color})
        else:
            self.emit({"type": "error", "error": "decision_timeout"})
            self._set_color(Color.RED)
            self.emit({"type": "done", "leader": False, "color": self.color})

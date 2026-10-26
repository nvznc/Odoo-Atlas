#!/usr/bin/env python3
"""Orquestador DAG para los subagentes de Atlas-Odoo-Studio.

El script compila un grafo de dependencias, detecta ciclos, ejecuta cada nodo
con timeout y reintentos, y guarda checkpoints para poder reanudar. Los
subagentes son de solo lectura y devuelven control al nodo padre.

Uso:
    python3 scripts/studio_dag.py --dry-run
    python3 scripts/studio_dag.py --execute
    python3 scripts/studio_dag.py --execute --resume
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
STATE_DIR: Final = ROOT / "var" / "studio_dag"
STATE_FILE: Final = STATE_DIR / "state.json"
LOG_DIR: Final = STATE_DIR / "logs"


@dataclass(slots=True)
class Node:
    """Nodo del DAG."""

    key: str
    agent: str
    prompt: str
    deps: tuple[str, ...] = ()
    timeout_s: int = 180
    max_retries: int = 1
    critical: bool = True
    artifact: str = ""


@dataclass(slots=True)
class NodeState:
    """Estado persistido de un nodo."""

    status: str = "pending"
    attempts: int = 0
    started_at: float | None = None
    ended_at: float | None = None
    returncode: int | None = None
    artifact: str = ""
    error: str = ""


@dataclass(slots=True)
class Dag:
    """Grafo acíclico dirigido de nodos."""

    nodes: dict[str, Node] = field(default_factory=dict)

    def add(self, node: Node) -> None:
        """Agrega un nodo validando duplicados."""
        if node.key in self.nodes:
            raise ValueError(f"Nodo duplicado: {node.key}")
        self.nodes[node.key] = node

    def validate(self) -> None:
        """Valida dependencias y detecta ciclos."""
        for node in self.nodes.values():
            missing = sorted(set(node.deps) - self.nodes.keys())
            if missing:
                raise ValueError(f"{node.key} depende de nodos inexistentes: {missing}")
        cycle = self.find_cycle()
        if cycle:
            raise ValueError(f"Ciclo detectado: {' -> '.join(cycle)}")

    def find_cycle(self) -> list[str] | None:
        """Devuelve la ruta de un ciclo usando DFS, o None."""
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []

        def visit(key: str) -> list[str] | None:
            if key in visiting:
                start = stack.index(key)
                return [*stack[start:], key]
            if key in visited:
                return None
            visiting.add(key)
            stack.append(key)
            for dep in self.nodes[key].deps:
                found = visit(dep)
                if found:
                    return found
            stack.pop()
            visiting.remove(key)
            visited.add(key)
            return None

        for key in self.nodes:
            found = visit(key)
            if found:
                return found
        return None

    def topological_waves(self) -> list[list[str]]:
        """Agrupa nodos en olas ejecutables en paralelo."""
        indegree = {key: len(node.deps) for key, node in self.nodes.items()}
        children: dict[str, set[str]] = {key: set() for key in self.nodes}
        for node in self.nodes.values():
            for dep in node.deps:
                children[dep].add(node.key)

        ready = sorted(key for key, degree in indegree.items() if degree == 0)
        waves: list[list[str]] = []
        while ready:
            waves.append(ready)
            next_ready: list[str] = []
            for key in ready:
                for child in sorted(children[key]):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        next_ready.append(child)
            ready = next_ready
        if sum(len(wave) for wave in waves) != len(self.nodes):
            raise ValueError("El grafo contiene un ciclo")
        return waves


def build_dag() -> Dag:
    """Construye el DAG de investigación de Atlas-Odoo-Studio."""
    dag = Dag()
    dag.add(
        Node(
            key="metadata",
            agent="studio-metadata-architect",
            prompt=(
                "Analiza el ORM y los metadatos de Odoo 19 para Atlas-Odoo-Studio. "
                "Devuelve hallazgos con archivo:línea, riesgos y recomendaciones."
            ),
            timeout_s=180,
            artifact="01_orm_metadata.md",
        )
    )
    dag.add(
        Node(
            key="features",
            agent="studio-feature-analyst",
            prompt=(
                "Analiza las funciones y la UX de Odoo Studio 19. Prioriza el MVP P0 "
                "para Atlas-Odoo-Studio y cita fuentes públicas."
            ),
            timeout_s=180,
            artifact="02_studio_features.md",
        )
    )
    dag.add(
        Node(
            key="views",
            agent="studio-view-architect",
            prompt=(
                "Diseña el motor de vistas y XPath de Atlas-Odoo-Studio sobre Odoo 19. "
                "Incluye riesgos de upgrade y ejemplos de extensiones."
            ),
            deps=("metadata", "features"),
            timeout_s=240,
            artifact="03_view_engine.md",
        )
    )
    dag.add(
        Node(
            key="owl",
            agent="studio-owl-architect",
            prompt=(
                "Diseña el editor OWL de Atlas-Odoo-Studio para Odoo 19. Incluye overlay, "
                "systray, preview, drag & drop, assets y tests."
            ),
            deps=("views", "features"),
            timeout_s=300,
            artifact="04_owl_editor.md",
        )
    )
    dag.add(
        Node(
            key="audit",
            agent="studio-quality-auditor",
            prompt=(
                "Audita el diseño y el código de Atlas-Odoo-Studio. Revisa seguridad, "
                "Ruff, tests, licencia y riesgos de upgrade. Usa el formato de hallazgos."
            ),
            deps=("metadata", "views", "owl", "features"),
            timeout_s=300,
            artifact="05_audit.md",
        )
    )
    dag.validate()
    return dag


def load_state() -> dict[str, NodeState]:
    """Carga el checkpoint si existe."""
    if not STATE_FILE.exists():
        return {}
    raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {key: NodeState(**value) for key, value in raw.items()}


def save_state(state: dict[str, NodeState]) -> None:
    """Guarda el checkpoint de forma atómica."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    payload = {key: asdict(value) for key, value in state.items()}
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_FILE)


def node_is_done(state: dict[str, NodeState], key: str) -> bool:
    """Indica si un nodo ya terminó correctamente."""
    return state.get(key, NodeState()).status == "ok"


async def run_agent(node: Node, attempt: int) -> tuple[int, str, str]:
    """Ejecuta un subagente de opencode con timeout.

    Devuelve (returncode, stdout, stderr). Si no existe el binario, devuelve
    un código distinto de cero con el error.
    """
    executable = shutil.which("opencode")
    if not executable:
        return 127, "", "No se encontró el ejecutable 'opencode' en PATH."

    command = [
        executable,
        "run",
        "--agent",
        node.agent,
        "--format",
        "json",
        "--dir",
        str(ROOT),
        node.prompt,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=ROOT,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=node.timeout_s,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return 124, "", f"Timeout de {node.timeout_s}s en el intento {attempt}."
    return process.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


async def run_node(
    node: Node,
    state: dict[str, NodeState],
    semaphore: asyncio.Semaphore,
    execute: bool,
) -> None:
    """Ejecuta un nodo respetando reintentos y checkpoints."""
    if node_is_done(state, node.key):
        print(f"[skip] {node.key}: ya completado")
        return

    current = state.setdefault(node.key, NodeState())
    if not execute:
        current.status = "planned"
        current.artifact = str(LOG_DIR / node.artifact)
        print(f"[plan] {node.key}: {node.agent} (timeout={node.timeout_s}s)")
        return

    async with semaphore:
        for attempt in range(1, node.max_retries + 2):
            current.status = "running"
            current.attempts = attempt
            current.started_at = time.time()
            current.error = ""
            save_state(state)
            print(f"[run ] {node.key}: intento {attempt}/{node.max_retries + 1}")
            returncode, stdout, stderr = await run_agent(node, attempt)
            current.returncode = returncode
            current.ended_at = time.time()

            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_path = LOG_DIR / f"{node.key}.attempt{attempt}.log"
            log_text = stdout + ("\n[stderr]\n" + stderr if stderr else "")
            log_path.write_text(log_text, encoding="utf-8")

            if returncode == 0:
                current.status = "ok"
                current.artifact = str(log_path)
                save_state(state)
                print(f"[ ok ] {node.key}: {log_path}")
                return
            current.status = "failed"
            current.error = stderr or stdout or f"returncode={returncode}"
            save_state(state)
            print(f"[fail] {node.key}: {current.error}")
            if returncode == 124:
                break
        if node.critical:
            raise RuntimeError(f"Nodo crítico fallido: {node.key}")


async def execute_dag(dag: Dag, execute: bool, resume: bool) -> int:
    """Ejecuta el DAG por olas."""
    state = load_state() if resume else {}
    if not resume:
        for node in dag.nodes.values():
            state[node.key] = NodeState()
        save_state(state)

    semaphore = asyncio.Semaphore(3)
    try:
        for wave in dag.topological_waves():
            print(f"[wave] {', '.join(wave)}")
            await asyncio.gather(
                *(run_node(dag.nodes[key], state, semaphore, execute) for key in wave)
            )
    except RuntimeError as error:
        print(f"[abort] {error}", file=sys.stderr)
        save_state(state)
        return 1
    save_state(state)
    if not execute:
        print("[dry-run] No se ejecutaron agentes.")
    return 0


def parse_args() -> argparse.Namespace:
    """Lee argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo muestra el plan.")
    mode.add_argument("--execute", action="store_true", help="Ejecuta los subagentes.")
    parser.add_argument("--resume", action="store_true", help="Reanuda desde el checkpoint.")
    return parser.parse_args()


def main() -> int:
    """Punto de entrada."""
    args = parse_args()
    dag = build_dag()
    waves = dag.topological_waves()
    if not args.execute:
        print("DAG de Atlas-Odoo-Studio")
        for index, wave in enumerate(waves, start=1):
            print(f"  ola {index}: {', '.join(wave)}")
        for node in dag.nodes.values():
            deps = ", ".join(node.deps) or "-"
            print(
                f"  {node.key:8} agente={node.agent:30} deps={deps:35} "
                f"timeout={node.timeout_s:3}s retries={node.max_retries}"
            )
        if args.dry_run or not args.execute:
            return asyncio.run(execute_dag(dag, execute=False, resume=args.resume))
    return asyncio.run(execute_dag(dag, execute=True, resume=args.resume))


if __name__ == "__main__":
    raise SystemExit(main())

# src/lms/orchestrator/cli.py
"""
CLI interface for the Orchestrator.

Provides a simple command-line interface for testing and interacting
with the orchestrator.

Usage:
    python -m src.lms.orchestrator.cli --help
    python -m src.lms.orchestrator.cli submit "Add pagination" --type development
    python -m src.lms.orchestrator.cli status
    python -m src.lms.orchestrator.cli run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

from src.mantle.orchestrator import Orchestrator, TaskType, TaskPriority


def get_orchestrator() -> Orchestrator:
    """Create and return an orchestrator instance."""
    load_dotenv()

    gemini_key = os.getenv("GEMINI_API_KEY")

    return Orchestrator(
        project_root=str(project_root),
        gemini_api_key=gemini_key,
        neo4j_db=None,  # CLI doesn't connect to Neo4j
    )


async def cmd_submit(args: argparse.Namespace) -> None:
    """Submit a new task."""
    orch = get_orchestrator()

    # Parse task type
    task_type_map = {
        "dev": TaskType.DEVELOPMENT,
        "development": TaskType.DEVELOPMENT,
        "lore": TaskType.LORE_MANAGEMENT,
        "analysis": TaskType.ANALYSIS,
        "maintenance": TaskType.MAINTENANCE,
    }
    task_type = task_type_map.get(args.type.lower(), TaskType.DEVELOPMENT)

    # Parse priority
    priority_map = {
        "critical": TaskPriority.CRITICAL,
        "high": TaskPriority.HIGH,
        "medium": TaskPriority.MEDIUM,
        "low": TaskPriority.LOW,
    }
    priority = priority_map.get(args.priority.lower(), TaskPriority.MEDIUM)

    task_id = await orch.submit_task(
        title=args.title,
        description=args.description or args.title,
        task_type=task_type,
        priority=priority,
        auto_decompose=not args.no_decompose,
    )

    print(f"Task submitted: {task_id}")
    print(f"  Title: {args.title}")
    print(f"  Type: {task_type.value}")
    print(f"  Priority: {priority.value}")


async def cmd_status(args: argparse.Namespace) -> None:
    """Show orchestrator status."""
    orch = get_orchestrator()
    status = await orch.get_status()

    print("Orchestrator Status")
    print("=" * 40)
    print(f"Session ID: {status['session_id'][:8]}...")
    print(f"Running: {status['is_running']}")
    print(f"Duration: {status['duration_seconds']:.1f}s")
    print()
    print("Queue Status:")
    qs = status["queue_status"]
    print(f"  Total: {qs['total_tasks']}")
    print(f"  Pending: {qs['pending']}")
    print(f"  Running: {qs['running']}")
    print(f"  Completed: {qs['completed']}")
    print(f"  Failed: {qs['failed']}")


async def cmd_run(args: argparse.Namespace) -> None:
    """Run all pending tasks."""
    orch = get_orchestrator()

    print("Running orchestrator...")
    print()

    result = await orch.run()

    print()
    print("Execution Complete")
    print("=" * 40)
    qs = result["queue_status"]
    print(f"Tasks completed: {qs['completed']}")
    print(f"Tasks failed: {qs['failed']}")
    print(f"Total tokens: {result['total_tokens_used']}")
    print(f"Duration: {result['duration_seconds']:.1f}s")


async def cmd_run_task(args: argparse.Namespace) -> None:
    """Run a single task by ID."""
    orch = get_orchestrator()

    print(f"Running task: {args.task_id}")

    try:
        result = await orch.run_single_task(args.task_id)

        print()
        print("Task Result")
        print("=" * 40)
        print(f"Status: {result.status.value}")
        print(f"Agent: {result.agent_id}")
        print(f"Time: {result.execution_time_ms}ms")

        if result.output:
            print()
            print("Output:")
            for key, value in result.output.items():
                print(f"  {key}: {value}")

        if result.warnings:
            print()
            print("Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        if result.error_message:
            print()
            print(f"Error: {result.error_message}")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


async def cmd_interactive(args: argparse.Namespace) -> None:
    """Interactive mode for submitting and running tasks."""
    orch = get_orchestrator()

    print("Orchestrator Interactive Mode")
    print("=" * 40)
    print("Commands:")
    print("  submit <title>  - Submit a new task")
    print("  status          - Show status")
    print("  run             - Run all tasks")
    print("  quit            - Exit")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break

        elif cmd == "submit":
            if len(parts) < 2:
                print("Usage: submit <title>")
                continue

            task_id = await orch.submit_task(
                title=parts[1],
                description=parts[1],
                auto_decompose=False,
            )
            print(f"Submitted: {task_id[:8]}...")

        elif cmd == "status":
            status = await orch.get_status()
            qs = status["queue_status"]
            print(f"Pending: {qs['pending']} | Completed: {qs['completed']} | Failed: {qs['failed']}")

        elif cmd == "run":
            result = await orch.run()
            qs = result["queue_status"]
            print(f"Done. Completed: {qs['completed']}, Failed: {qs['failed']}")

        else:
            print(f"Unknown command: {cmd}")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Orchestrator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a new task")
    submit_parser.add_argument("title", help="Task title")
    submit_parser.add_argument("-d", "--description", help="Task description")
    submit_parser.add_argument(
        "-t", "--type",
        default="development",
        choices=["dev", "development", "lore", "analysis", "maintenance"],
        help="Task type",
    )
    submit_parser.add_argument(
        "-p", "--priority",
        default="medium",
        choices=["critical", "high", "medium", "low"],
        help="Task priority",
    )
    submit_parser.add_argument(
        "--no-decompose",
        action="store_true",
        help="Don't auto-decompose the task",
    )

    # status command
    subparsers.add_parser("status", help="Show orchestrator status")

    # run command
    subparsers.add_parser("run", help="Run all pending tasks")

    # run-task command
    run_task_parser = subparsers.add_parser("run-task", help="Run a specific task")
    run_task_parser.add_argument("task_id", help="Task ID to run")

    # interactive command
    subparsers.add_parser("interactive", help="Interactive mode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Run the appropriate command
    if args.command == "submit":
        asyncio.run(cmd_submit(args))
    elif args.command == "status":
        asyncio.run(cmd_status(args))
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "run-task":
        asyncio.run(cmd_run_task(args))
    elif args.command == "interactive":
        asyncio.run(cmd_interactive(args))


if __name__ == "__main__":
    main()

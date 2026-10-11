"""Command line runner for the agent team.

    .venv/bin/python -m backend.run_team --ticket 101
    .venv/bin/python -m backend.run_team            # whole open board
    .venv/bin/python -m backend.run_team --reset    # copy the original DB over the working copy first
"""

import argparse
import asyncio
import shutil

from backend.config import ORIGINAL_DB_PATH, WORKING_DB_PATH
from backend.models import TeamRunRequest
from backend.team import run_team


def reset_database() -> None:
    shutil.copyfile(ORIGINAL_DB_PATH, WORKING_DB_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--ticket", type=int, default=None, help="ticket id (default: all open tickets)")
    parser.add_argument("--instructions", default="", help="extra instructions for the Boss")
    parser.add_argument("--reset", action="store_true", help="reset data/campus_customs_new.db from the original first")
    args = parser.parse_args()

    if args.reset:
        reset_database()
        print("Reset data/campus_customs_new.db from data/campus_customs.db")

    result = asyncio.run(run_team(TeamRunRequest(ticket_id=args.ticket, instructions=args.instructions)))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

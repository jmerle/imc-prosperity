import json
import sys
from pathlib import Path

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: ranking.py <archipelago round json file>")
        sys.exit(1)

    teams = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    teams = sorted(teams, key=lambda team: (-team["profit"], team["team"]["name"].lower()))

    joint_rank = 0
    joint_profit = -1
    next_joint_rank = 1

    for team in teams:
        if team["profit"] != joint_profit:
            joint_rank = next_joint_rank
            joint_profit = team["profit"]

        team["jointRank"] = joint_rank
        next_joint_rank += 1

    default_current_place = next(team["currentPlace"] for team in teams if team["profit"] < 0)
    teams = sorted(teams, key=lambda team: team["currentPlace"] or default_current_place)

    print(f"# IMC Prosperity Round 1 Ranking ({len(teams):,.0f} teams)")
    print()
    print(f"Ranks are shown in official and joint format. The official rank does not have joint places for teams with equal profits, the joint rank does.")
    print()
    print("| Official Rank | Joint Rank | Team | Profit |")
    print("| ------------- | ---------- | ---- | ------ |")

    for team in teams:
        official_rank = f"{team['currentPlace']:,.0f}" if team["currentPlace"] is not None else "None"
        print(f"| {official_rank} | {team['jointRank']:,.0f} | {team['team']['name']} | {team['profit']:,.2f} |")

if __name__ == "__main__":
    main()

import subprocess

def solve_pddl(domain_file: str, problem_file: str) -> list:
    JAVA17_PATH = "/usr/lib/jvm/java-17-openjdk-amd64/bin/java"
    ENHSP_JAR = "lby/json_for_pddl/enhsp.jar"

    try:
        result = subprocess.run(
            [
                JAVA17_PATH,
                "-jar",
                ENHSP_JAR,
                "-o", domain_file,
                "-f", problem_file
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        print("=== Return code ===")
        print(result.returncode)
        print("=== STDOUT ===")
        print(result.stdout)
        print("=== STDERR ===")
        print(result.stderr)
        if result.returncode != 0:
            print("Solver failed. Stderr:")
            print(result.stderr)
            return None

        lines = result.stdout.splitlines()
        plan_lines = []
        plan_started = False

        for line in lines:
            if plan_started:
                if line.strip():
                    plan_lines.append(line.strip())
            if line.strip().startswith("0."):
                plan_started = True
                plan_lines.append(line.strip())

        return plan_lines

    except Exception as e:
        print("ENHSP failed:", e)
        return None


def main():
    domain_file = "domain.pddl"
    problem_file = "problem_wooden_axe.pddl"

    plan = solve_pddl(domain_file, problem_file)
    if plan:
        print("Solution plan:")
        for step in plan:
            print(step)
    else:
        print("No plan found or solver failed.")


if __name__ == "__main__":
    main()

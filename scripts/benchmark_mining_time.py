import argparse
import statistics
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.block import Block


def mine_once(difficulty: int) -> float:
    block = Block(
        index=1,
        previous_hash="0" * 64,
        transactions=[],
        difficulty=difficulty,
        timestamp=0,
        nonce=0,
    )
    start = time.perf_counter()
    block.mine()
    elapsed = time.perf_counter() - start
    return max(elapsed, 1e-12)


def format_duration(value: float) -> str:
    if value <= 0:
        return "0.000s"
    if value < 1e-3:
        return f"{value:.3e}s"
    return f"{value:.3f}s"


def benchmark_difficulty_range(min_difficulty: int, max_difficulty: int, trials: int):
    results = []
    for difficulty in range(min_difficulty, max_difficulty + 1):
        timings = [mine_once(difficulty) for _ in range(trials)]
        average_time = statistics.mean(timings)
        std_dev = statistics.stdev(timings) if len(timings) > 1 else 0.0
        results.append((difficulty, average_time, std_dev, timings))
    return results


def plot_results(results, output_path: str):
    difficulties = [item[0] for item in results]
    average_times = [item[1] for item in results]
    std_devs = [item[2] for item in results]

    plt.figure(figsize=(9, 5))
    plt.errorbar(
        difficulties,
        average_times,
        yerr=std_devs,
        fmt="o-",
        linewidth=2,
        color="#2563eb",
        ecolor="#2563eb",
        elinewidth=1.5,
        capsize=4,
        label="Average mining time ± std dev",
    )
    for difficulty, average_time, std_dev in zip(difficulties, average_times, std_devs):
        plt.annotate(
            f"μ={format_duration(average_time)}\nσ={format_duration(std_dev)}",
            (difficulty, average_time),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            va="bottom",
        )
    plt.title("Mining Time vs Difficulty")
    plt.xlabel("Difficulty")
    plt.ylabel("Average mining time (seconds, log scale)")
    plt.xticks(difficulties)
    plt.yscale("log")
    plt.ylim(1e-12, max(average_times) * 10)
    plt.grid(True, which="both", linestyle="--", alpha=0.4)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)


def main():
    parser = argparse.ArgumentParser(description="Measure how mining time depends on difficulty and plot the result.")
    parser.add_argument("--min-difficulty", type=int, default=1, help="Starting difficulty level")
    parser.add_argument("--max-difficulty", type=int, default=5, help="Ending difficulty level")
    parser.add_argument("--trials", type=int, default=3, help="Number of runs per difficulty")
    parser.add_argument("--output", default="mining_time_vs_difficulty.png", help="Output image path")
    args = parser.parse_args()

    if args.min_difficulty < 1:
        raise ValueError("min-difficulty must be at least 1")
    if args.max_difficulty < args.min_difficulty:
        raise ValueError("max-difficulty must be greater than or equal to min-difficulty")
    if args.trials < 1:
        raise ValueError("trials must be at least 1")

    print(
        f"Benchmarking mining time from difficulty {args.min_difficulty} to {args.max_difficulty} "
        f"with {args.trials} trial(s) per difficulty..."
    )

    results = benchmark_difficulty_range(args.min_difficulty, args.max_difficulty, args.trials)
    for difficulty, average_time, std_dev, timings in results:
        per_trial = ", ".join(f"{value:.6f}s" for value in timings)
        print(
            f"difficulty={difficulty}: average={average_time:.6f}s | std_dev={std_dev:.6f}s | "
            f"trials=[{per_trial}]"
        )

    plot_results(results, args.output)
    print(f"Saved chart to {args.output}")


if __name__ == "__main__":
    main()

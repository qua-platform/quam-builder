"""HTML report generation utilities for RB timing analysis."""

import base64
import io
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def generate_rb_timing_report(
    rb_config,
    theory: dict,
    timing: dict,
    setup_time: float,
    output_dir: str = None,
    output_filename: str = None,
) -> str:
    """Generate an HTML report with timing analysis and plots.

    Args:
        rb_config: RB configuration dataclass.
        theory: Theoretical timing calculations.
        timing: Measured timing results.
        setup_time: Time to set up the experiment.
        output_dir: Directory for output file. Defaults to 'data' folder.
        output_filename: Output filename. Defaults to timestamped name.

    Returns:
        Path to the generated HTML file.
    """
    # Set up output directory
    if output_dir is None:
        output_dir = Path(__file__).parent / "data"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up output filename
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"rb_timing_report_{timestamp}.html"

    output_path = output_dir / output_filename

    # Create plots and encode as base64
    timing_breakdown_img = _create_timing_breakdown_plot(theory, timing)
    execution_comparison_img = _create_execution_comparison_plot(theory, timing)
    iteration_times_img = _create_iteration_times_plot(timing)

    # Calculate derived values
    avg_gates_per_clifford = 1.875
    physical_fraction = 0.6
    overhead_factor = timing["rb_execution_only"] / theory["theoretical_total_s"]
    unexplained_time = timing["rb_execution_only"] - theory["theoretical_total_s"]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RB Timing Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}
        .value {{
            font-family: 'Monaco', 'Menlo', monospace;
            color: #0066cc;
        }}
        .highlight {{
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #ffc107;
        }}
        .plot {{
            text-align: center;
            margin: 20px 0;
        }}
        .plot img {{
            max-width: 100%;
            height: auto;
        }}
        .summary-box {{
            display: inline-block;
            padding: 15px 25px;
            margin: 10px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-box.blue {{ background: #e3f2fd; }}
        .summary-box.green {{ background: #e8f5e9; }}
        .summary-box.orange {{ background: #fff3e0; }}
        .summary-box.red {{ background: #ffebee; }}
        .summary-box .number {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .summary-box .label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        .timestamp {{
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <h1>Single-Qubit RB Timing Report</h1>
    <p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

    <div class="card">
        <h2>Summary</h2>
        <div style="text-align: center;">
            <div class="summary-box blue">
                <div class="number">{timing['rb_avg']:.3f} s</div>
                <div class="label">Average Execution Time</div>
            </div>
            <div class="summary-box green">
                <div class="number">{theory['theoretical_total_s']:.3f} s</div>
                <div class="label">Theoretical Minimum</div>
            </div>
            <div class="summary-box orange">
                <div class="number">{timing['latency_estimate']:.3f} s</div>
                <div class="label">Communication Latency</div>
            </div>
            <div class="summary-box red">
                <div class="number">{overhead_factor:.2f}x</div>
                <div class="label">Overhead Factor</div>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>RB Configuration</h2>
            <table>
                <tr><th>Parameter</th><th>Value</th></tr>
                <tr><td>Circuit Depths</td><td class="value">{rb_config.circuit_lengths}</td></tr>
                <tr><td>Number of Depths</td><td class="value">{len(rb_config.circuit_lengths)}</td></tr>
                <tr><td>Circuits per Depth</td><td class="value">{rb_config.num_circuits_per_length}</td></tr>
                <tr><td>Shots per Circuit</td><td class="value">{rb_config.num_shots}</td></tr>
                <tr><td>Total Sequences</td><td class="value">{theory['total_sequences']:,}</td></tr>
                <tr><td>Average Cliffords</td><td class="value">{theory['avg_cliffords']:.1f}</td></tr>
                <tr><td>Random Seed</td><td class="value">{rb_config.seed}</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>Timing Configuration</h2>
            <table>
                <tr><th>Parameter</th><th>Value</th></tr>
                <tr><td>Init Duration</td><td class="value">{rb_config.init_duration_ns/1000:.1f} µs</td></tr>
                <tr><td>Measure Duration</td><td class="value">{rb_config.measure_duration_ns/1000:.1f} µs</td></tr>
                <tr><td>Compensation Duration</td><td class="value">{rb_config.compensation_duration_ns/1000:.1f} µs</td></tr>
                <tr><td>Gate Duration</td><td class="value">{rb_config.gate_duration_ns} ns</td></tr>
                <tr><td>RF Readout Duration</td><td class="value">{rb_config.rf_readout_duration_ns/1000:.1f} µs</td></tr>
            </table>
        </div>
    </div>

    <div class="card">
        <h2>Gate Statistics</h2>
        <table>
            <tr><th>Parameter</th><th>Value</th><th>Notes</th></tr>
            <tr>
                <td>Avg Gates per Clifford</td>
                <td class="value">{avg_gates_per_clifford}</td>
                <td>For basis {{sx, x, rz}}</td>
            </tr>
            <tr>
                <td>Physical Gate Fraction</td>
                <td class="value">{physical_fraction*100:.0f}%</td>
                <td>X90, X180, Y90, Y180 (not virtual Z)</td>
            </tr>
            <tr>
                <td>Physical Gates per Clifford</td>
                <td class="value">{avg_gates_per_clifford * physical_fraction:.2f}</td>
                <td>Gates that take time</td>
            </tr>
            <tr>
                <td>Avg Gate Time per Sequence</td>
                <td class="value">{theory['avg_gate_time_us']:.2f} µs</td>
                <td>For {theory['avg_cliffords']:.1f} avg Cliffords</td>
            </tr>
        </table>
    </div>

    <div class="card">
        <h2>Timing Breakdown Plot</h2>
        <div class="plot">
            <img src="data:image/png;base64,{timing_breakdown_img}" alt="Timing Breakdown">
        </div>
    </div>

    <div class="card">
        <h2>Execution Time Comparison</h2>
        <div class="plot">
            <img src="data:image/png;base64,{execution_comparison_img}" alt="Execution Comparison">
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Theoretical Timing</h2>
            <table>
                <tr><th>Component</th><th>Per Sequence</th><th>Total</th></tr>
                <tr>
                    <td>Initialization</td>
                    <td class="value">{theory['init_time_us']:.1f} µs</td>
                    <td class="value">{theory['init_time_us'] * theory['total_sequences'] / 1000:.1f} ms</td>
                </tr>
                <tr>
                    <td>Gates</td>
                    <td class="value">{theory['avg_gate_time_us']:.2f} µs</td>
                    <td class="value">{theory['avg_gate_time_us'] * theory['total_sequences'] / 1000:.1f} ms</td>
                </tr>
                <tr>
                    <td>Measurement</td>
                    <td class="value">{theory['measure_time_us']:.1f} µs</td>
                    <td class="value">{theory['measure_time_us'] * theory['total_sequences'] / 1000:.1f} ms</td>
                </tr>
                <tr>
                    <td>Compensation</td>
                    <td class="value">{theory['compensation_time_us']:.1f} µs</td>
                    <td class="value">{theory['compensation_time_us'] * theory['total_sequences'] / 1000:.1f} ms</td>
                </tr>
                <tr style="font-weight: bold; background: #f0f0f0;">
                    <td>Total</td>
                    <td class="value">{theory['time_per_sequence_ms']:.3f} ms</td>
                    <td class="value">{theory['theoretical_total_s']*1000:.2f} ms</td>
                </tr>
            </table>
        </div>

        <div class="card">
            <h2>Measured Timing</h2>
            <table>
                <tr><th>Measurement</th><th>Value</th></tr>
                <tr>
                    <td>Setup Time</td>
                    <td class="value">{setup_time*1000:.2f} ms</td>
                </tr>
                <tr>
                    <td>Communication Latency</td>
                    <td class="value">{timing['latency_estimate']*1000:.2f} ms</td>
                </tr>
                <tr>
                    <td>RB Execution (total)</td>
                    <td class="value">{timing['rb_avg']*1000:.2f} ms ± {timing['rb_std']*1000:.2f}</td>
                </tr>
                <tr>
                    <td>RB Execution (minus latency)</td>
                    <td class="value">{timing['rb_execution_only']*1000:.2f} ms</td>
                </tr>
                <tr>
                    <td>Unexplained Overhead</td>
                    <td class="value">{unexplained_time*1000:.2f} ms</td>
                </tr>
            </table>
        </div>
    </div>

    <div class="card">
        <h2>Individual Iteration Times</h2>
        <div class="plot">
            <img src="data:image/png;base64,{iteration_times_img}" alt="Iteration Times">
        </div>
        <div class="grid">
            <div>
                <h3>Minimal Wait Program</h3>
                <table>
                    <tr><th>Iteration</th><th>Time (ms)</th></tr>
                    {"".join(f'<tr><td>{i+1}</td><td class="value">{t*1000:.2f}</td></tr>' for i, t in enumerate(timing['wait_times']))}
                    <tr style="font-weight: bold;"><td>Average</td><td class="value">{timing['wait_avg']*1000:.2f} ± {timing['wait_std']*1000:.2f}</td></tr>
                </table>
            </div>
            <div>
                <h3>RB Program</h3>
                <table>
                    <tr><th>Iteration</th><th>Time (ms)</th></tr>
                    {"".join(f'<tr><td>{i+1}</td><td class="value">{t*1000:.2f}</td></tr>' for i, t in enumerate(timing['rb_times']))}
                    <tr style="font-weight: bold;"><td>Average</td><td class="value">{timing['rb_avg']*1000:.2f} ± {timing['rb_std']*1000:.2f}</td></tr>
                </table>
            </div>
        </div>
    </div>

    <div class="card highlight">
        <h2>Analysis</h2>
        <p>
            The measured RB execution time of <strong>{timing['rb_avg']:.3f} s</strong>
            is <strong>{overhead_factor:.2f}x</strong> the theoretical minimum of
            <strong>{theory['theoretical_total_s']:.3f} s</strong>.
        </p>
        <p>
            After subtracting the estimated communication latency of
            <strong>{timing['latency_estimate']:.3f} s</strong>, the actual execution
            time is approximately <strong>{timing['rb_execution_only']:.3f} s</strong>.
        </p>
        <p>
            The unexplained overhead of <strong>{unexplained_time:.3f} s</strong>
            ({unexplained_time/theory['theoretical_total_s']*100:.1f}% of theoretical time)
            may be attributed to:
        </p>
        <ul>
            <li>QUA compilation and program loading</li>
            <li>Switch/case branching overhead in the gate loop</li>
            <li>Stream processing and data transfer</li>
            <li>Alignment operations between elements</li>
        </ul>
    </div>
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html_content)

    return str(output_path)


def _create_timing_breakdown_plot(theory: dict, timing: dict) -> str:
    """Create a stacked bar chart showing timing breakdown."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Theoretical breakdown (per sequence, scaled to total)
    total_seqs = theory["total_sequences"]
    components = ["Init", "Gates", "Measure", "Compensation"]
    theoretical_values = [
        theory["init_time_us"] * total_seqs / 1000,
        theory["avg_gate_time_us"] * total_seqs / 1000,
        theory["measure_time_us"] * total_seqs / 1000,
        theory["compensation_time_us"] * total_seqs / 1000,
    ]

    # Colors
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]

    # Create stacked bar for theoretical
    bottom = 0
    for comp, val, color in zip(components, theoretical_values, colors):
        ax.bar(
            "Theoretical\nMinimum", val, bottom=bottom, color=color, label=comp, edgecolor="white"
        )
        bottom += val

    # Measured breakdown
    latency = timing["latency_estimate"] * 1000
    execution = timing["rb_execution_only"] * 1000
    theoretical_total = theory["theoretical_total_s"] * 1000
    overhead = execution - theoretical_total

    ax.bar(
        "Measured\n(with latency)",
        latency,
        color="#f44336",
        label="Comm. Latency",
        edgecolor="white",
    )
    ax.bar(
        "Measured\n(with latency)",
        theoretical_total,
        bottom=latency,
        color="#8BC34A",
        label="Theoretical Exec.",
        edgecolor="white",
    )
    ax.bar(
        "Measured\n(with latency)",
        overhead,
        bottom=latency + theoretical_total,
        color="#FFC107",
        label="Other Overhead",
        edgecolor="white",
    )

    ax.set_ylabel("Time (ms)")
    ax.set_title("Timing Breakdown")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1))

    plt.tight_layout()

    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return img_base64


def _create_execution_comparison_plot(theory: dict, timing: dict) -> str:
    """Create a bar chart comparing theoretical vs measured execution times."""
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ["Theoretical\nMinimum", "Measured\n(minus latency)", "Measured\n(total)"]
    values = [
        theory["theoretical_total_s"] * 1000,
        timing["rb_execution_only"] * 1000,
        timing["rb_avg"] * 1000,
    ]
    colors = ["#4CAF50", "#2196F3", "#FF5722"]

    bars = ax.bar(categories, values, color=colors, edgecolor="white", linewidth=2)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 5,
            f"{val:.1f} ms",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_ylabel("Time (ms)")
    ax.set_title("Execution Time Comparison")
    ax.set_ylim(0, max(values) * 1.15)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return img_base64


def _create_iteration_times_plot(timing: dict) -> str:
    """Create a plot showing individual iteration times."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Wait program times
    iterations = range(1, len(timing["wait_times"]) + 1)
    ax1.bar(
        iterations, [t * 1000 for t in timing["wait_times"]], color="#9C27B0", edgecolor="white"
    )
    ax1.axhline(
        y=timing["wait_avg"] * 1000,
        color="red",
        linestyle="--",
        label=f'Mean: {timing["wait_avg"]*1000:.1f} ms',
    )
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Time (ms)")
    ax1.set_title("Minimal Wait Program")
    ax1.legend()

    # RB program times
    iterations = range(1, len(timing["rb_times"]) + 1)
    ax2.bar(iterations, [t * 1000 for t in timing["rb_times"]], color="#2196F3", edgecolor="white")
    ax2.axhline(
        y=timing["rb_avg"] * 1000,
        color="red",
        linestyle="--",
        label=f'Mean: {timing["rb_avg"]*1000:.1f} ms',
    )
    ax2.set_xlabel("Iteration")
    ax2.set_ylabel("Time (ms)")
    ax2.set_title("RB Program")
    ax2.legend()

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return img_base64

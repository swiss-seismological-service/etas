import json
import sys
import matplotlib.pyplot as plt

"""
Plots the simulations vs execution time for different core counts.
Takes a json file as input, resulting from the run_entrypoint_bench.py script.
"""

def plot_simulations_vs_execution_time(json_file):
    with open(json_file, 'r') as file:
        data = json.load(file)

    core_dict = {}
    for entry in data:
        cores = entry['cores']
        simulations = entry['simulations']
        execution_time = entry['execution_time']

        if cores not in core_dict:
            core_dict[cores] = {'simulations': [], 'execution_time': []}

        core_dict[cores]['simulations'].append(simulations)

        # ugly hack to allow timestamps and seconds in floats
        execution_time = entry['execution_time']
        if isinstance(execution_time, str):
            h, m, s = map(float, entry['execution_time'].split(':'))
            execution_time = h * 3600 + m * 60 + s
        core_dict[cores]['execution_time'].append(execution_time)

    for cores, values in core_dict.items():
        plt.scatter(values['simulations'],
                    values['execution_time'], label=f'Cores: {cores}')
        plt.xscale('log')
        # plt.yscale('log')

    plt.xlabel('Simulations')
    plt.ylabel('Execution Time')
    plt.title('Simulations vs Execution Time for Different Core Counts')
    plt.legend()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python plot_results.py <path_to_json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    plot_simulations_vs_execution_time(json_file)

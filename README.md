# Blockchain Project

## Quick Start

To run three nodes simultaneously, execute the following script in your terminal:

```bash
./scripts/run_nodes.bat
```

To stop all running nodes, execute:

```bash
./scripts/stop_nodes.bat
```

To run the web explorer page, execute:

```bash
./scripts/run_explorer.bat
```

## Running Utility Scripts

To run individual utility scripts from the project root, first set the PYTHONPATH in your PowerShell terminal:

```bash
$env:PYTHONPATH = (Get-Location).Path
```

To generate a mining time versus difficulty graph, execute:
```bash
python .\scripts\benchmark_mining_time.py --min-difficulty 1 --max-difficulty 5 --trials 3 --output .\scripts\mining_time_vs_difficulty.png
```

To sign a transaction using a specific private key, execute:

```bash
python .\scripts\sign_transaction.py --sender 907ba938752ccae947411d8b07ef50d116041273481ffde25d717063d840abd4 --recipient cf5aa0115b4a32a9f87160f01f0c2c1b9e5aadb8d62f7c6b21c43debc81d2c7b --amount 10 --fee 1 --nonce 0 --private-key ca0b3178e45cedb1784a2d747c5bb8f29addb5e744ceb941c8524f757fa1457b
```
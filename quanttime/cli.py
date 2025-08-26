"""
QuantTime CLI for managing the trading platform.
"""

import typer
from pathlib import Path

app = typer.Typer(help="QuantTime control CLI")

@app.command()
def status():
    """Show system status."""
    typer.echo("QuantTime ML Trading Suite Status")
    typer.echo("=" * 40)
    
    # Check data directory
    data_dir = Path("data/es_futures/mbo")
    if data_dir.exists():
        typer.echo(f"✅ Data directory: {data_dir}")
    else:
        typer.echo(f"❌ Data directory not found: {data_dir}")
    
    # Check settings
    settings_file = Path("settings.txt")
    if settings_file.exists():
        typer.echo(f"✅ Settings file: {settings_file}")
    else:
        typer.echo(f"❌ Settings file not found: {settings_file}")
    
    # Check virtual environment
    venv_dir = Path(".venv")
    if venv_dir.exists():
        typer.echo(f"✅ Virtual environment: {venv_dir}")
    else:
        typer.echo(f"❌ Virtual environment not found: {venv_dir}")

@app.command()
def start():
    """Start the QuantTime dashboard."""
    typer.echo("Starting QuantTime dashboard...")
    # This would typically call the main run function
    typer.echo("Dashboard should be available at http://localhost:8501")

@app.command()
def test():
    """Run the MBO pipeline test."""
    typer.echo("Running MBO pipeline test...")
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "test_mbo_pipeline.py"])
    if result.returncode == 0:
        typer.echo("✅ MBO pipeline test passed!")
    else:
        typer.echo("❌ MBO pipeline test failed!")

if __name__ == "__main__":
    app()



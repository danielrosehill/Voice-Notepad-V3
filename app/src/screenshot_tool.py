#!/usr/bin/env python3
"""Screenshot tool for Voice Notepad - captures UI screenshots for releases."""

import sys
import tomllib
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor


def get_version() -> str:
    """Get version from pyproject.toml."""
    project_root = Path(__file__).parent.parent.parent
    pyproject = project_root / "pyproject.toml"

    if pyproject.exists():
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("version", "unknown")
    return "unknown"


def create_grid_composite(images: list[Path], output_path: Path, cols: int = 3):
    """Create a grid composite from multiple images."""
    pixmaps = [QPixmap(str(img)) for img in images]

    if not pixmaps:
        return

    # Calculate grid dimensions
    rows = (len(pixmaps) + cols - 1) // cols

    # Use first image to determine cell size
    cell_width = pixmaps[0].width()
    cell_height = pixmaps[0].height()

    # Add padding between images
    padding = 10

    # Create composite
    total_width = cols * cell_width + (cols - 1) * padding
    total_height = rows * cell_height + (rows - 1) * padding

    composite = QPixmap(total_width, total_height)
    composite.fill(QColor(240, 240, 240))  # Light gray background

    painter = QPainter(composite)

    for i, pixmap in enumerate(pixmaps):
        row = i // cols
        col = i % cols
        x = col * (cell_width + padding)
        y = row * (cell_height + padding)
        painter.drawPixmap(x, y, pixmap)

    painter.end()
    composite.save(str(output_path))


def take_screenshots(output_dir: Path, window):
    """Capture screenshots of all tabs and settings dialog."""
    from src.main import SettingsDialog

    screenshots = []
    main_tabs = []

    # Tab names for filenames
    tab_names = ["record", "history", "cost", "analysis", "models", "mic-test", "about"]

    # Capture each tab
    for i, name in enumerate(tab_names):
        window.tabs.setCurrentIndex(i)
        QApplication.processEvents()

        pixmap = window.grab()
        filepath = output_dir / f"{i+1}-{name}.png"
        pixmap.save(str(filepath))
        screenshots.append(filepath)
        main_tabs.append(filepath)
        print(f"  Captured: {filepath.name}")

    # Capture Settings dialog (each tab)
    settings_tabs = ["api-keys", "audio", "behavior", "hotkeys"]
    dialog = SettingsDialog(window.config, window.recorder, window)
    dialog.show()
    QApplication.processEvents()

    # Find the tabs widget in the dialog
    tabs_widget = None
    for child in dialog.findChildren(type(window.tabs)):
        tabs_widget = child
        break

    if tabs_widget:
        for i, name in enumerate(settings_tabs):
            tabs_widget.setCurrentIndex(i)
            QApplication.processEvents()

            pixmap = dialog.grab()
            filepath = output_dir / f"settings-{i+1}-{name}.png"
            pixmap.save(str(filepath))
            screenshots.append(filepath)
            print(f"  Captured: {filepath.name}")

    dialog.close()

    # Create two composite strips (2 images side by side each)
    # Composite 1: Record + History
    composite1_path = output_dir / "composite-1.png"
    print(f"  Creating: composite-1.png (record + history)")
    create_grid_composite([main_tabs[0], main_tabs[1]], composite1_path, cols=2)
    screenshots.append(composite1_path)

    # Composite 2: Cost + Analysis
    composite2_path = output_dir / "composite-2.png"
    print(f"  Creating: composite-2.png (cost + analysis)")
    create_grid_composite([main_tabs[2], main_tabs[3]], composite2_path, cols=2)
    screenshots.append(composite2_path)

    return screenshots


def main():
    # Get version and create underscore format for folder name
    version = get_version()
    version_folder = version.replace(".", "_")

    # Determine output directory
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / "screenshots" / version_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Voice Notepad Screenshot Tool")
    print(f"Version: {version}")
    print(f"Output: screenshots/{version_folder}/")
    print()

    # Create app and window
    app = QApplication(sys.argv)

    from src.main import MainWindow

    window = MainWindow()
    window.show()
    QApplication.processEvents()

    def capture_and_exit():
        print("Capturing screenshots...")
        screenshots = take_screenshots(output_dir, window)
        print(f"\nCaptured {len(screenshots)} files")

        # List files
        print(f"\nFiles:")
        for f in sorted(output_dir.glob("*.png")):
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name} ({size_kb:.1f} KB)")

        app.quit()

    QTimer.singleShot(500, capture_and_exit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

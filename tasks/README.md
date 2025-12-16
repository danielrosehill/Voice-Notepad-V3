# Voice Notepad V3 - Task Scripts

Quick access to common development and build tasks.

## Available Tasks

### Development

```bash
./tasks/dev
```
Run the app from source in development mode (no installation needed).

### Building

```bash
./tasks/build              # Build .deb (default)
./tasks/build --deb        # Build Debian package
./tasks/build --appimage   # Build AppImage
./tasks/build --tarball    # Build portable tarball
./tasks/build --all        # Build all formats
./tasks/build --dev        # Fast dev build (no compression)
```

### Installing

```bash
./tasks/install
```
Install the latest .deb package from `dist/` directory.

### Release Workflow

```bash
./tasks/release            # Patch release (1.0.0 -> 1.0.1)
./tasks/release minor      # Minor release (1.0.0 -> 1.1.0)
./tasks/release major      # Major release (1.0.0 -> 2.0.0)
./tasks/release --deb-only # Patch release, .deb only (faster)
```

This command:
1. Bumps version in `pyproject.toml`
2. Takes screenshots
3. Builds packages
4. Shows next steps for git tagging

### Testing

```bash
./tasks/test
```
Run test suite:
- Syntax check all Python files
- Verify database integrity
- Check dependencies
- Test module imports

### Cleaning

```bash
./tasks/clean
```
Remove build artifacts, cache files, and temporary files.

## Typical Workflows

### Daily Development
```bash
./tasks/dev
# Make changes, test, repeat
```

### Creating a Release
```bash
# Make your changes
git add .
git commit -m "Add new feature"

# Create release build
./tasks/release minor

# Test the packages
./tasks/install

# Commit and tag
git add pyproject.toml
git commit -m "Bump version to 1.1.0"
git tag v1.1.0
git push && git push --tags
```

### Quick Build & Test
```bash
./tasks/build --dev
./tasks/install
# Test the installed version
```

## Directory Structure

```
tasks/
├── README.md      # This file
├── build          # Build packages
├── install        # Install latest .deb
├── release        # Create release build
├── dev            # Run from source
├── test           # Run tests
└── clean          # Clean artifacts
```

## Notes

- All tasks should be run from the repository root or tasks directory
- Tasks use relative paths and will work from either location
- Build outputs go to `dist/` directory
- Virtual environment is created automatically in `app/.venv`

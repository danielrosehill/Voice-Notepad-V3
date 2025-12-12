#!/bin/bash
# Incremental build script for Voice Notepad V3
# Bumps version and rebuilds the .deb package

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get current version from pyproject.toml
get_version() {
    grep 'version = ' "$PROJECT_DIR/pyproject.toml" | head -1 | cut -d'"' -f2
}

# Bump version (major.minor.patch)
bump_version() {
    local current="$1"
    local bump_type="${2:-patch}"

    IFS='.' read -r major minor patch <<< "$current"

    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch|*)
            patch=$((patch + 1))
            ;;
    esac

    echo "$major.$minor.$patch"
}

# Update version in pyproject.toml
update_version() {
    local new_version="$1"

    sed -i "s/^version = \".*\"/version = \"$new_version\"/" "$PROJECT_DIR/pyproject.toml"
    log_info "Updated pyproject.toml to version $new_version"
}

# Check for uncommitted changes
check_git_status() {
    cd "$PROJECT_DIR"

    if ! git diff --quiet HEAD -- 2>/dev/null; then
        log_warn "You have uncommitted changes"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Run basic tests
run_tests() {
    log_info "Running basic import test..."

    cd "$PROJECT_DIR"

    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi

    # Test that the module imports without errors
    if python3 -c "from src import config, audio_recorder, transcription, hotkeys" 2>/dev/null; then
        log_info "Import test passed"
    else
        log_error "Import test failed"
        exit 1
    fi
}

# Create git tag for version
create_git_tag() {
    local version="$1"
    local tag="v$version"

    cd "$PROJECT_DIR"

    if git rev-parse "$tag" >/dev/null 2>&1; then
        log_warn "Tag $tag already exists, skipping"
    else
        read -p "Create git tag $tag? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            git tag -a "$tag" -m "Release $version"
            log_info "Created tag $tag"
        fi
    fi
}

# Show usage
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [BUMP_TYPE]

Incremental build script for Voice Notepad V3.
Optionally bumps version before building.

BUMP_TYPE:
    patch   Increment patch version (x.x.X) [default]
    minor   Increment minor version (x.X.0)
    major   Increment major version (X.0.0)
    none    Don't bump version, just rebuild

OPTIONS:
    -h, --help      Show this help
    -n, --no-tag    Don't create git tag
    -t, --test      Run tests before building
    -v, --version   Show current version and exit

Examples:
    $(basename "$0")              # Bump patch and build
    $(basename "$0") minor        # Bump minor and build
    $(basename "$0") none         # Just rebuild current version
    $(basename "$0") -t patch     # Test, bump patch, and build
EOF
}

# Main
main() {
    local bump_type="patch"
    local create_tag=true
    local run_test=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -n|--no-tag)
                create_tag=false
                shift
                ;;
            -t|--test)
                run_test=true
                shift
                ;;
            -v|--version)
                echo "Current version: $(get_version)"
                exit 0
                ;;
            major|minor|patch|none)
                bump_type="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    cd "$PROJECT_DIR"

    local current_version=$(get_version)
    log_info "Current version: $current_version"

    # Check git status
    check_git_status

    # Run tests if requested
    if $run_test; then
        run_tests
    fi

    # Bump version if not 'none'
    local new_version="$current_version"
    if [ "$bump_type" != "none" ]; then
        new_version=$(bump_version "$current_version" "$bump_type")
        log_info "Bumping version: $current_version -> $new_version"
        update_version "$new_version"
    fi

    # Build the package
    log_info "Building .deb package..."
    "$SCRIPT_DIR/build-deb.sh"

    # Create git tag
    if $create_tag && [ "$bump_type" != "none" ]; then
        create_git_tag "$new_version"
    fi

    echo ""
    log_info "Build complete!"
    echo ""
    echo "Package: dist/voice-notepad_${new_version}_all.deb"
    echo ""
    echo "Next steps:"
    echo "  1. Test the package: sudo apt install ./dist/voice-notepad_${new_version}_all.deb"
    echo "  2. Commit changes: git add -A && git commit -m 'Release v$new_version'"
    echo "  3. Push with tags: git push && git push --tags"
}

main "$@"

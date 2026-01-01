#!/bin/bash
# Voice Notepad - Unified Release Script
#
# Interactive CLI for releasing new versions. Performs all steps in sequence:
# 1. Prompts for release type (minor/major)
# 2. Increments version automatically
# 3. Builds .deb package
# 4. Installs on local machine
# 5. Commits version bump
# 6. Creates git tag
# 7. Pushes to GitHub (triggers release workflow)
#
# Usage: ./release.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get current version from pyproject.toml
get_current_version() {
    grep -Po '(?<=^version = ")[^"]+' pyproject.toml
}

# Calculate new version based on bump type
calculate_new_version() {
    local current="$1"
    local bump_type="$2"

    IFS='.' read -r MAJOR MINOR PATCH <<< "$current"

    case "$bump_type" in
        major)
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        minor)
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        patch)
            PATCH=$((PATCH + 1))
            ;;
    esac

    echo "$MAJOR.$MINOR.$PATCH"
}

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}           ${BOLD}Voice Notepad - Release Manager${NC}                  ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print step
print_step() {
    local step_num="$1"
    local step_desc="$2"
    echo ""
    echo -e "${CYAN}[$step_num]${NC} ${BOLD}$step_desc${NC}"
    echo -e "${CYAN}────────────────────────────────────────${NC}"
}

# Print success
print_success() {
    echo -e "    ${GREEN}✓${NC} $1"
}

# Print info
print_info() {
    echo -e "    ${BLUE}→${NC} $1"
}

# Print warning
print_warning() {
    echo -e "    ${YELLOW}⚠${NC} $1"
}

# Print error and exit
print_error() {
    echo -e "    ${RED}✗${NC} $1"
    exit 1
}

# Main script
main() {
    print_header

    # Get current version
    CURRENT_VERSION=$(get_current_version)
    echo -e "Current version: ${BOLD}v$CURRENT_VERSION${NC}"
    echo ""

    # Calculate preview versions
    MINOR_VERSION=$(calculate_new_version "$CURRENT_VERSION" "minor")
    MAJOR_VERSION=$(calculate_new_version "$CURRENT_VERSION" "major")
    PATCH_VERSION=$(calculate_new_version "$CURRENT_VERSION" "patch")

    # Interactive selection
    echo -e "${BOLD}Select release type:${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} Minor release  → ${GREEN}v$MINOR_VERSION${NC}  (new features, backwards compatible)"
    echo -e "  ${CYAN}2)${NC} Major release  → ${GREEN}v$MAJOR_VERSION${NC}  (breaking changes)"
    echo -e "  ${CYAN}3)${NC} Patch release  → ${GREEN}v$PATCH_VERSION${NC}  (bug fixes only)"
    echo ""
    echo -e "  ${CYAN}q)${NC} Quit"
    echo ""

    read -p "Enter choice [1-3, q]: " choice

    case "$choice" in
        1)
            BUMP_TYPE="minor"
            NEW_VERSION="$MINOR_VERSION"
            ;;
        2)
            BUMP_TYPE="major"
            NEW_VERSION="$MAJOR_VERSION"
            ;;
        3)
            BUMP_TYPE="patch"
            NEW_VERSION="$PATCH_VERSION"
            ;;
        q|Q)
            echo ""
            echo "Release cancelled."
            exit 0
            ;;
        *)
            echo ""
            echo -e "${RED}Invalid choice. Exiting.${NC}"
            exit 1
            ;;
    esac

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  Releasing ${BOLD}v$CURRENT_VERSION${NC} → ${GREEN}${BOLD}v$NEW_VERSION${NC} (${BUMP_TYPE})"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Confirm
    read -p "Continue? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Release cancelled."
        exit 0
    fi

    # ===== STEP 1: Update version =====
    print_step "1/6" "Updating version numbers"

    # Update pyproject.toml
    sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
    print_success "Updated pyproject.toml"

    # Update fallback version in about_widget.py
    if [ -f "app/src/about_widget.py" ]; then
        sed -i "s/^_FALLBACK_VERSION = \".*\"/_FALLBACK_VERSION = \"$NEW_VERSION\"/" app/src/about_widget.py
        print_success "Updated about_widget.py"
    fi

    # ===== STEP 2: Build .deb =====
    print_step "2/6" "Building Debian package"

    print_info "Running build (this may take a moment)..."
    if ./scripts/build/deb.sh "$NEW_VERSION" > /tmp/build.log 2>&1; then
        print_success "Built voice-notepad_${NEW_VERSION}_amd64.deb"
    else
        echo ""
        cat /tmp/build.log
        print_error "Build failed. See output above."
    fi

    # ===== STEP 3: Install locally =====
    print_step "3/6" "Installing on local machine"

    print_info "Installing package (may require sudo password)..."
    if sudo dpkg -i "dist/voice-notepad_${NEW_VERSION}_amd64.deb" > /tmp/install.log 2>&1; then
        print_success "Installed v$NEW_VERSION locally"
    else
        # Try to fix dependencies
        sudo apt-get install -f -y >> /tmp/install.log 2>&1 || true
        print_success "Installed v$NEW_VERSION locally (fixed dependencies)"
    fi

    # ===== STEP 4: Commit version bump =====
    print_step "4/6" "Committing version changes"

    git add pyproject.toml
    [ -f "app/src/about_widget.py" ] && git add app/src/about_widget.py

    git commit -m "chore: bump version to $NEW_VERSION" > /dev/null 2>&1
    print_success "Committed version bump"

    # ===== STEP 5: Create git tag =====
    print_step "5/6" "Creating git tag"

    TAG_NAME="v$NEW_VERSION"
    git tag -a "$TAG_NAME" -m "Release $TAG_NAME"
    print_success "Created tag $TAG_NAME"

    # ===== STEP 6: Push to GitHub =====
    print_step "6/6" "Pushing to GitHub"

    print_info "Pushing commits..."
    git push > /dev/null 2>&1
    print_success "Pushed commits to origin"

    print_info "Pushing tag (triggers release workflow)..."
    git push origin "$TAG_NAME" > /dev/null 2>&1
    print_success "Pushed tag $TAG_NAME"

    # ===== Complete =====
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✓ Release v$NEW_VERSION complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}Local:${NC}    Installed and ready to use"
    echo -e "  ${BOLD}GitHub:${NC}   Release workflow triggered"
    echo ""
    echo -e "  View release: ${CYAN}https://github.com/danielrosehill/Voice-Notepad/releases/tag/$TAG_NAME${NC}"
    echo ""
}

# Run main
main "$@"

#!/usr/bin/env bash
# update-changelog.sh
# Generates CHANGELOG.rst from git tags and commits.
#
# Usage: update-changelog.sh [--bump <major|minor|patch>]
#   --bump: How to increment version for unreleased commits (default: patch)

set -euo pipefail

# Parse arguments
bump_type="patch"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bump)
            if [[ $# -lt 2 ]]; then
                echo "Error: --bump requires an argument (major|minor|patch)" >&2
                exit 1
            fi
            bump_type="$2"
            if [[ ! "$bump_type" =~ ^(major|minor|patch)$ ]]; then
                echo "Error: --bump must be one of: major, minor, patch" >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            echo "Usage: $0 [--bump <major|minor|patch>]" >&2
            exit 1
            ;;
    esac
done

repo_url=$(git remote get-url origin | sed 's/\.git$//' | sed 's|git@github\.com:|https://github.com/|')

outfile="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/CHANGELOG.rst"

{
    echo "========="
    echo "Changelog"
    echo "========="

    mapfile -t tag_array < <(git tag --sort=-creatordate | grep '^v')

    # Check if there are unreleased commits
    if [[ ${#tag_array[@]} -gt 0 ]]; then
        latest_tag="${tag_array[0]}"
        unreleased_count=$(git rev-list --count "$latest_tag"..HEAD)

        if ((unreleased_count > 0)); then
            # Compute next version based on bump type
            version="${latest_tag#v}"
            IFS='.' read -r major minor patch <<< "$version"

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
                patch)
                    patch=$((patch + 1))
                    ;;
            esac

            next_version="${major}.${minor}.${patch}"
            current_date=$(date +%Y-%m-%d)

            # Add next version section
            title="Version $next_version ($current_date)"
            underline=$(printf '=%.0s' $(seq 1 ${#title}))

            echo "$title"
            echo "$underline"
            echo ""

            delim="---COMMIT_DELIM---"
            raw=$(git log --format="${delim}%h %s%n%b" "$latest_tag"..HEAD)

            # Process unreleased commits
            while IFS= read -r -d $'\x00' entry; do
                [[ -z "${entry// /}" ]] && continue

                first_line=$(echo "$entry" | head -n1 | sed 's/^[[:space:]]*//')

                if [[ "$first_line" =~ ^([0-9a-f]+)[[:space:]]+(.+)$ ]]; then
                    hash="${BASH_REMATCH[1]}"
                    subject="${BASH_REMATCH[2]}"
                else
                    continue
                fi

                hash_link="\`$hash <$repo_url/commit/$hash>\`_"

                mapfile -t body_lines < <(echo "$entry" | tail -n +2 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$' || true)

                if ((${#body_lines[@]} > 0)); then
                    echo "- $hash_link $subject"
                    echo ""
                    for ((b = 0; b < ${#body_lines[@]}; b++)); do
                        echo "  ${body_lines[$b]}"
                        if ((b < ${#body_lines[@]} - 1)); then
                            echo ""
                        fi
                    done
                    echo ""
                else
                    echo "- $hash_link $subject"
                fi
            done < <(echo "$raw" | perl -e "
                local \$/;
                my \$input = <STDIN>;
                my @parts = split(/\Q$delim\E/, \$input);
                shift @parts;
                for my \$p (@parts) {
                    \$p =~ s/\s+\$//;
                    print \$p . \"\0\";
                }
            ")

            echo ""
        fi
    fi

    for ((i = 0; i < ${#tag_array[@]}; i++)); do
        tag="${tag_array[$i]}"
        version="${tag#v}"
        date=$(git log -1 --format="%ai" "$tag" | cut -d' ' -f1)

        title="Version $version ($date)"
        underline=$(printf '=%.0s' $(seq 1 ${#title}))

        echo "$title"
        echo "$underline"
        echo ""

        if ((i < ${#tag_array[@]} - 1)); then
            range="${tag_array[$((i + 1))]}..$tag"
        else
            range="$tag"
        fi

        delim="---COMMIT_DELIM---"
        raw=$(git log --format="${delim}%h %s%n%b" "$range")

        # Split on delimiter, process each commit
        # Use perl for reliable multi-char delimiter splitting
        while IFS= read -r -d $'\x00' entry; do
            [[ -z "${entry// /}" ]] && continue

            # First line has hash + subject
            first_line=$(echo "$entry" | head -n1 | sed 's/^[[:space:]]*//')

            if [[ "$first_line" =~ ^([0-9a-f]+)[[:space:]]+(.+)$ ]]; then
                hash="${BASH_REMATCH[1]}"
                subject="${BASH_REMATCH[2]}"
            else
                continue
            fi

            hash_link="\`$hash <$repo_url/commit/$hash>\`_"

            # Collect non-empty body lines
            mapfile -t body_lines < <(echo "$entry" | tail -n +2 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$' || true)

            if ((${#body_lines[@]} > 0)); then
                echo "- $hash_link $subject"
                echo ""
                for ((b = 0; b < ${#body_lines[@]}; b++)); do
                    echo "  ${body_lines[$b]}"
                    if ((b < ${#body_lines[@]} - 1)); then
                        echo ""
                    fi
                done
                echo ""
            else
                echo "- $hash_link $subject"
            fi
        done < <(echo "$raw" | perl -e "
            local \$/;
            my \$input = <STDIN>;
            my @parts = split(/\Q$delim\E/, \$input);
            shift @parts;  # first element is empty
            for my \$p (@parts) {
                \$p =~ s/\s+\$//;
                print \$p . \"\0\";
            }
        ")

        echo ""
    done
} > "$outfile"

echo "CHANGELOG.rst updated successfully."

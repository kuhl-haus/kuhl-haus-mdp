#!/usr/bin/env bash
# update-changelog.sh
# Generates CHANGELOG.rst from git tags and commits.

set -euo pipefail

repo_url=$(git remote get-url origin | sed 's/\.git$//' | sed 's|git@github\.com:|https://github.com/|')

outfile="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/CHANGELOG.rst"

{
    echo "========="
    echo "Changelog"
    echo "========="

    mapfile -t tag_array < <(git tag --sort=-creatordate | grep '^v')

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

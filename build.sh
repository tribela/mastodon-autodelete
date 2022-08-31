#!/bin/bash

set -eo pipefail

build_path=$(mktemp -d)
# shellcheck disable=SC2064
trap "rm -rf $build_path" EXIT
rsync -au --info=progress2 --delete --filter=':- .gitignore' ./ "$build_path"
cd "$build_path" || exit 1
git reset --
git checkout .
git clean -fdx
docker buildx build --cache-from "kjwon15/mastodon-autodelete:buildcache" --cache-to "kjwon15/mastodon-autodelete:buildcache" --pull -t "kjwon15/mastodon-autodelete" . "$@"

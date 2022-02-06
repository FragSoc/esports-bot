#!/bin/bash

use_docker=0

while getopts ":d" flag; do
    case "${flag}" in
        d) use_docker=1;;
    esac
done

echo "Updating bot to latest version..."

if test $use_docker == 1; then
	docker-compose down
fi

git pull
git checkout master
latest_tag=$(git describe --tags)
echo "Latest tag on master is: $latest_tag"
git checkout tags/$latest_tag --quiet

if test -f "src/esportsbot/version.txt"; then
	rm "src/esportsbot/version.txt"
fi

echo latest_tag >> src/esportsbot/version.txt
if $use_docker == 1; then
	docker-compose up --build --detach
fi
echo "Done updating esportsbot to $latest_tag!"

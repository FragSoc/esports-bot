#!/usr/bin/env bash

branch=$(git branch --show)
docker_tag="fragsoc/esports-bot:${branch}"

docker tag fragsoc/esports-bot ${docker_tag}
docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}
docker push fragsoc/esports-bot

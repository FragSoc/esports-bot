#!/usr/bin/env bash

docker tag fragsoc/esports-bot fragsoc/esports-bot:${DOCKER_TAG}
echo ${DOCKER_PASSWORD} | docker login -u ${DOCKER_USERNAME} --password-stdin
docker push fragsoc/esports-bot

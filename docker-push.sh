#!/usr/bin/env bash

docker tag fragsoc/esports-bot fragsoc/esports-bot:${DOCKER_TAG}
docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}
docker push fragsoc/esports-bot

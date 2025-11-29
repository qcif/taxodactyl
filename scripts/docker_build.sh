#!/usr/bin/env bash

set -e

PUSH=false
IMAGE=neoformit/taxodactyl
DOCKERFILE="Dockerfile"

while getopts "t:pu" opt; do
  case $opt in
    t)
      TAG=$OPTARG  # Tag to use for the build
      ;;
    p)
      PUSH=true  # Whether to push the image after building
      ;;
    u)
      DOCKERFILE="Dockerfile.update"  # Code update only
      ;;
    *)
      ;;
  esac
done

if [[ -z $TAG ]]; then
  TAG="v$(cat VERSION)"
  read -p "Have you updated the VERSION file? (read '${TAG}') [y/n] > " REPLY
  if [[ $REPLY != "y" ]]; then
    echo "Please update the VERSION file before building."
    exit 1
  fi
fi

docker build -t $IMAGE:$TAG -f $DOCKERFILE .
docker tag $IMAGE:$TAG $IMAGE:latest

if [ "$PUSH" = true ]; then
  docker push $IMAGE:$TAG
  docker push $IMAGE:latest
fi

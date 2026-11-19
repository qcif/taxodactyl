#!/usr/bin/env bash

set -e

PUSH=false
LATEST=false
IMAGE=neoformit/taxodactyl
DOCKERFILE="Dockerfile"

while getopts "t:plu" opt; do
  case $opt in
    t)
      TAG=$OPTARG  # Tag to use for the build
      ;;
    p)
      PUSH=true  # Whether to push the image after building
      ;;
    l)
      LATEST=true  # Also tag (and push, with -p) as latest
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

if [ "$LATEST" = true ]; then
  docker tag $IMAGE:$TAG $IMAGE:latest
fi

if [ "$PUSH" = true ]; then
  docker push $IMAGE:$TAG
  if [ "$LATEST" = true ]; then
    docker push $IMAGE:latest
  fi
fi

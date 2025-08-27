#!/usr/bin/env bash

set -e

PUSH=false
IMAGE=neoformit/taxodactyl

while getopts "t:p" opt; do
  case $opt in
    t)
      TAG=$OPTARG
      ;;
    p)
      PUSH=true
      ;;
    *)
      ;;
  esac
done

if [[ -z $TAG ]]; then
  TAG=$(cat ../VERSION)
  read -p "Have you updated the VERSION file? (read '${TAG}') [y/n] > " REPLY
  if [[ $REPLY != "y" ]]; then
    echo "Please update the VERSION file before building."
    exit 1
  fi
fi

docker build -t $IMAGE:$TAG .
docker tag $IMAGE:$TAG $IMAGE:latest

if [ "$PUSH" = true ]; then
  docker push $IMAGE:$TAG
  docker push $IMAGE:latest
fi

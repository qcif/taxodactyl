#!/usr/bin/env bash

set -e

PUSH=false
IMAGE=neoformit/taxodactyl

# Check for -t argument and set TAG if provided
while getopts "t:" opt; do
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
  # Prompt for the tag if not provided
  read -p "Have you updated the VERSION file? [y/n] > " REPLY
  if [[ $REPLY != "y" ]]; then
    echo "Please update the VERSION file before building."
    exit 1
  fi
  TAG=$(cat ../VERSION)
fi

docker build -t $IMAGE:$TAG .
docker tag $IMAGE:$TAG $IMAGE:latest

if [ "$PUSH" = true ]; then
  docker push $IMAGE:$TAG
  docker push $IMAGE:latest
fi

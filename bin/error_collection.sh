#!/bin/bash

job_name=$1
cd /mnt/data/cloudgene/workspace/${job_name}
nextflow log last -f process,workdir -F 'exit != 0' | awk -F'\t' '
$1 ~ /^QCIF/ {
  printf "\nProcess: %s\n", $1
  printf "Workdir: %s\n", $2

  stderr_file = $2 "/.command.err"
  stdout_file = $2 "/.command.out"

  printf "Last 10 lines of stderr:\n"
  system("tail -n 10 " stderr_file)

  printf "\nLast 10 lines of stdout:\n"
  system("tail -n 10 " stdout_file)

  print "-----------------------------"
}'


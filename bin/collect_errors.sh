#!/bin/bash

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      execution_folder="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# This Bash script snippet is a common pattern for parsing command-line arguments. The while [[ $# -gt 0 ]]; do ... done loop continues as long as there are arguments left ($# is the number of arguments). Inside the loop, the case "$1" in ... esac statement checks the value of the first argument ($1). If it matches --dir, the script sets the variable execution_folder to the value of the second argument ($2), then uses shift 2 to remove both the flag and its value from the argument list. For any other argument, the script simply uses shift to skip it.

# This approach allows the script to process arguments in order, handling known flags (like --dir) and ignoring unknown ones. A subtle point is that shift 2 is only safe if you know the flag is always followed by a value; otherwise, you might accidentally skip arguments. This pattern is useful for simple argument parsing, but for more complex needs, dedicated tools like getopts or external libraries are recommended.

if [[ -n "$execution_folder" ]]; then
  cd "${execution_folder}" || exit 1
fi

nextflow log last -f process,workdir,tag -F 'exit != 0' | awk -F'\t' '
{
  printf "\nProcess: %s\n", $1
  printf "Tag: %s\n", $3
  printf "Workdir: %s\n", $2

  stderr_file = $2 "/.command.err"
  stdout_file = $2 "/.command.out"

  printf "Last 10 lines of stderr:\n"
  system("tail -n 10 " stderr_file)

  printf "\nLast 10 lines of stdout:\n"
  system("tail -n 10 " stdout_file)

  print "-----------------------------"
}'
# $1 ~ /^QCIF/ 

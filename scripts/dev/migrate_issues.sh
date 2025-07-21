#!/bin/bash

set -e

SRC_REPO="qcif/daff-biosecurity-wf2"
DEST_REPO="qcif/taxodactyl"

# Skip the first issue because it was done manually
issue_numbers=$(gh issue list --repo qcif/daff-biosecurity-wf2 --json number --state all   | jq '.[].number' | tail -n +2)

for i in $issue_numbers; do
  echo "Migrating issue #${i}..."
  gh issue transfer $i --repo $SRC_REPO $DEST_REPO
done

# Issues transferred:
#133 -> 30
#131 -> 31
#130 -> 32
#129 -> 33
#128 -> 34
#127 -> 35
#126 -> 36
#125 -> 37
#124 -> 38
#123 -> 39
#122 -> 40
#121 -> 41
#120 -> 42
#119 -> 43
#118 -> 44
#117 -> 45
#116 -> 46
#115 -> 47
#114 -> 48
#113 -> 49
#112 -> 50
#111 -> 51
#110 -> 52
#108 -> 53
#106 -> 54
#105 -> 55
#104 -> 56
#101 -> 57
#100 -> 58
#99 -> 59

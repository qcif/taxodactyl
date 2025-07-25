#!/bin/bash

set -e

SRC_REPO="qcif/daff-biosecurity-wf2"
DEST_REPO="qcif/taxodactyl"

issue_numbers=$(gh issue list --repo qcif/daff-biosecurity-wf2 --json number --limit 1000 --state all   | jq '.[].number')

for i in $issue_numbers; do
  echo "Migrating issue #${i}..."
  gh issue transfer $i --repo $SRC_REPO $DEST_REPO
done

# Issues transferred:
#133 -> 30
#132 -> 60
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
#98 -> 61
#97 -> 62
#96 -> 63
#95 -> 64
#94 -> 65
#93 -> 66
#92 -> 67
#91 -> 68
#90 -> 69
#89 -> 70
#88 -> 71
#87 -> 72
#86 -> 73
#85 -> 74
#82 -> 75
#80 -> 76
#79 -> 77
#78 -> 78
#77 -> 79
#76 -> 80
#75 -> 81
#74 -> 82
#73 -> 83
#81 -> 84
#71 -> 85
#70 -> 86
#69 -> 87
#67 -> 88
#66 -> 89
#65 -> 90
#64 -> 91
#63 -> 92
#62 -> 93
#61 -> 94
#60 -> 95
#59 -> 96
#58 -> 97
#55 -> 98
#54 -> 99
#53 -> 100
#52 -> 101
#51 -> 102
#50 -> 103
#49 -> 104
#48 -> 105
#47 -> 106
#46 -> 107
#45 -> 108
#44 -> 109
#43 -> 110
#41 -> 111
#39 -> 112
#38 -> 113
#37 -> 114
#36 -> 115
#35 -> 116
#34 -> 117
#33 -> 118
#32 -> 119
#31 -> 120
#30 -> 121
#29 -> 122
#28 -> 123
#27 -> 124
#26 -> 125
#25 -> 126
#24 -> 127
#23 -> 128
#21 -> 129
#19 -> 130
#18 -> 131
#17 -> 132
#16 -> 133
#15 -> 134
#14 -> 135
#13 -> 136
#12 -> 137
#11 -> 138
#10 -> 139

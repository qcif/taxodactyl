test_case=scenario_04
# update=" --update-snapshot"
update=""
index=""

version=CUSTOMISE
taxo_fold=CUSTOMISE/${version}
tests_fold=CUSTOMISE/tests/${version}/${test_case}${index}

# Keep the original config intact and only copy it for a fresh run.
# Uncomment only for the first run
# cp nf-test.config nf-test_ORIGINAL.config

mkdir -p CUSTOMISE
mkdir -p ${tests_fold}

cd ${taxo_fold}
cp nf-test_ORIGINAL.config nf-test.config
# Substitute the test output location and scenario name before running nf-test.
sed -i "s|CUSTOMISE|\"$tests_fold\"|g" nf-test.config
sed -i "s|SCENARIO|"${test_case}"|g" nf-test.config

# Capture nf-test stdout/stderr so later steps can parse the results.
nf-test test test/${test_case}/taxodactyl.workflow.nf.test $update \
> ${tests_fold}/nf-test_results.txt \
2> ${tests_fold}/nf-test_errors.txt

# Extract short hash from the "Test [xxxxxxxx]" line.
test_hash_prefix=$(sed 's/\x1b\[[0-9;]*m//g' "${tests_fold}/nf-test_results.txt" \
	| sed -n "s/^ *Test \[\([0-9a-fA-F]\{8\}\)\].*/\1/p" \
	| head -n 1 \
	| tr '[:upper:]' '[:lower:]')

if [[ -n "$test_hash_prefix" ]]; then
	# Save the hash prefix so downstream scripts can find the matching snapshot dir.
	echo "$test_hash_prefix" > "$tests_fold/nf-test_hash.txt"
	echo "Saved test hash prefix to $tests_fold/nf-test_hash.txt: $test_hash_prefix"
else
	echo "Warning: unable to extract hash from nf-test output" >&2
fi

# Convert nf-test JSON snapshot errors into a CSV review file.
python3 ${taxo_fold}/bin/diff_json_snapshot_to_csv.py $tests_fold/nf-test_errors.txt

baseline_dir=${taxo_fold}/test/${test_case}/flags
evaluated_dir=${tests_fold}/tests/${test_hash_prefix}*
mkdir -p ${tests_fold}/flags/evaluated

# Compare the evaluated flags against the baseline test flags.
bash ${taxo_fold}/bin/collect_flags.sh $evaluated_dir $tests_fold/flags/evaluated
python3 ${taxo_fold}/bin/test_flags.py $baseline_dir $tests_fold/flags/evaluated \
    > $tests_fold/flags_results.txt \
    2> $tests_fold/flags_errors.txt

# Return to the shared scripts directory for the next step in the workflow.
cd /mnt/data/tests-wf-2/scripts
**Download pipeline**
Enter the folder where you want the pipeline to be and run the following:
```
git clone https://github.com/qcif/nf-daff-biosecurity-wf2.git
```
If you want to run a specific version, add a branch to the command (see tags for available versions), e.g.
```
git clone https://github.com/qcif/nf-daff-biosecurity-wf2.git --branch v0.1.0
```

**Display help**
```
nextflow run /path/to/pipeline/nf-daff-biosecurity-wf2/main.nf --help
```
Include hidden parameters
```
nextflow run /path/to/pipeline/nf-daff-biosecurity-wf2/main.nf --help --show_hidden
```

**Step by step bash commands**
If you have never downloaded or run a Nextflow pipeline, these bash commands can help you set it up and run it for the first time. 


```bash
# Define the version of the pipeline to use
version="v1.0.0"

# Define the main folder where all operations will take place
main_folder=/home/ubuntu

# Define the pipeline folder and tests folder paths
pipeline_folder=${main_folder}/daff-biosecurity-wf2
tests_folder=${main_folder}/daff-biosec-wf2_tests

# Get today's date in the format YYYYMMDD
today=$(date +"%Y%m%d")

# Create the pipeline folder if it doesn't exist
mkdir -p $pipeline_folder

# Change directory to the pipeline folder
cd $pipeline_folder

# Clone the specific branch of the pipeline repository from GitHub
git clone https://github.com/qcif/nf-daff-biosecurity-wf2.git --branch ${version}

# Rename the cloned repository folder to match the version
mv nf-daff-biosecurity-wf2 $version

# Create the tests folder if it doesn't exist
mkdir -p $tests_folder

# Change directory to the tests folder
cd $tests_folder

# Create a results folder inside the tests folder
mkdir -p results

# Create a configuration folder inside the tests folder
mkdir -p conf

# Create a Nextflow configuration file for the pipeline
cat <<EOF > conf/${version}.config
singularity {
    cacheDir = '$pipeline_folder/sig_images/'
}
cleanup = true
EOF

# Create an input folder inside the tests folder
mkdir -p input

# Create a sample sequence file in the input folder
cat <<EOF > input/barcode84_seq.fasta
>barcode84_contig1_PE250203-B_REP1_KAPA
ACACTATATTTTATTTTTGGTATTTGAGCAGGAATATTAGGAACATCATTAAGTATTTTAATTCGTATAGAATTGGGAACTCCTGGATCTTTAATCGGGGATGATCAAATCTATAATACTATTGTTACAGCTCATGCTTTTATTATAATTTTTTTTATAGTAATACCTATTATAATTGGAGGGTTTGGAAATTGATTAATTCCTCTAATATTAGGAGCACCTGACATAGCTTTCCCACGAATAAATAATATAAGATTTTGATTATTACCCCCATCACTAATATTACTAATTTCAAGAAGAATTGTAGAAAATGGAGCAGGAACTGGATGAACAGTGTACCCCCCTCTGTCATCTAATATTGCTCATAGTGGATCTTCCGTTGATCTAGCAATCTTCTCTCTTCATTTAGCAGGAATTTCATCAATTTTAGGAGCCATTAACTTTATCACAACTATTATTAATATAAAAGTAAATAATTTATCTTTTGATCAAATATCATTATTTATTTGAGCTGTTGGTATTACTGCATTATTATTATTATTATCTTTACCAGTATTAGCTGGAGCTATTACAATATTATTAACAGATCGTAATTTAAACACATCATTTTTTGACCCCGCTGGAGGAGGAGACCCAATTCTTTATCAACATTTATTTTGATTTTT
EOF

# Create a metadata file in the input folder
cat <<EOF > input/barcode84_metadata.csv
sample_id,locus,preliminary_id,taxa_of_interest,host,country
barcode84_contig1_PE250203-B_REP1_KAPA,CO1,Lycaenidae,Chilades pandava,NA,Australia
EOF

# Create a launch folder for the current version and date
mkdir -p launch/${version}_${today}

# Create a script to run the pipeline in the launch folder
cat <<EOF > launch/${version}_${today}/run.sh
#!/bin/bash 
nextflow run $pipeline_folder/$version/main.nf \\
    --metadata $tests_folder/input/barcode84_metadata.csv \\
    --sequences $tests_folder/input/barcode84_seq.fasta \\
    --blastdb $main_folder/Database_BLAST_20231204/core_nt_20250220/2025-02-11-01-05-02/core_nt \\
    --outdir $tests_folder/results/${version}_${today} \\
    -profile singularity \\
    --taxdb $pipeline_folder/taxdump/ \\
    --ncbi_api_key 426055072298f36c9d1b95c2327df4d8c808 \\
    --user_email shaun.bochow@aff.gov.au \\
    --analyst_name "Shaun Bochow" \\
    --facility_name "DAFF Biosecurity, Cairns" \\
    -c $tests_folder/conf/v0.2.4-patch.config \\
    -resume
EOF

# Make the run script executable
chmod +x launch/${version}_${today}/run.sh

# Change directory to the launch folder
cd launch/${version}_${today}

# Execute the run script to start the pipeline
./run.sh
```
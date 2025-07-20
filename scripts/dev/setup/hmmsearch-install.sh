#!/bin/bash

set -e

wget http://eddylab.org/software/hmmer/hmmer-3.4.tar.gz
tar -xzf hmmer-3.4.tar.gz
rm hmmer-3.4.tar.gz
cd hmmer-3.4
./configure --prefix=$HOME/.local/hmmer
make
make install
strip $HOME/.local/hmmer/bin/hmmsearch
find $HOME/.local/hmmer/bin ! -name 'hmmsearch' -type f -delete
cp $HOME/.local/hmmer/bin/hmmsearch ~/.local/bin
strip ~/.local/bin/hmmsearch
cd ..
rm -rf hmmer-3.4/

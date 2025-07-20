FROM python:3.12

RUN apt update && apt install -y nano less

# Install taxonkit
RUN wget https://github.com/shenwei356/taxonkit/releases/latest/download/taxonkit_linux_amd64.tar.gz \
    && tar -zxvf taxonkit_linux_amd64.tar.gz \
    && mv taxonkit /usr/local/bin/ \
    && rm taxonkit_linux_amd64.tar.gz

# Install HMMSearch
RUN wget http://eddylab.org/software/hmmer/hmmer-3.4.tar.gz \
    && tar -xzf hmmer-3.4.tar.gz \
    && rm hmmer-3.4.tar.gz \
    && cd hmmer-3.4 \
    && ./configure --prefix=/opt/hmmer \
    && make \
    && make install \
    && strip /opt/hmmer/bin/hmmsearch \
    && find /opt/hmmer/bin ! -name 'hmmsearch' -type f -delete \
    && cp /opt/hmmer/bin/hmmsearch /usr/local/bin \
    && strip /usr/local/bin/hmmsearch \
    && cd .. \
    && rm -rf hmmer-3.4/

COPY . /app/scripts

RUN pip install -r /app/scripts/requirements.txt

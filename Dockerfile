FROM phusion/baseimage:0.9.18

MAINTAINER Luke Campbell <luke.campbell@rpsgroup.com>

# General dependencies:
RUN apt-get update && \
    apt-get install -y wget git build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install conda/python
RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet https://repo.continuum.io/miniconda/Miniconda3-4.0.5-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    export PATH="/opt/conda/bin:${PATH}" && \
    conda config --set always_yes yes --set changeps1 no && \
    conda config --set show_channel_urls True && \
    conda config --add create_default_packages pip && \
    echo 'conda 4.0.*' >> /opt/conda/conda-meta/pinned && \
    conda update conda && \
    conda config --add channels conda-forge && \
    conda clean --all --yes

ENV PATH=/opt/conda/bin:$PATH

COPY sensorml2iso /usr/lib/sensorml2iso/sensorml2iso
COPY LICENSE README.md requirements.txt setup.py /usr/lib/sensorml2iso/

RUN useradd -m harvester
RUN conda install --file /usr/lib/sensorml2iso/requirements.txt && \
    conda clean --all --yes && \
    pip install --upgrade pip

RUN pip install -e /usr/lib/sensorml2iso

RUN mkdir -p /srv/iso && \
    chmod 777 /srv/iso

COPY ./contrib/init /etc/my_init.d
COPY ./contrib/config/config.json /etc/sensorml2iso/config.json

VOLUME /srv/iso

CMD ["/sbin/my_init"]

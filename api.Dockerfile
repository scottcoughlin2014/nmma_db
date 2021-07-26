FROM ubuntu:20.04
#FROM python:3.7
#FROM python:3.7-slim

ENV TZ=America/Chicago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends sudo apt-utils && \
    apt-get install -y --no-install-recommends \
        gcc libopenmpi-dev openmpi-bin openmpi-common openmpi-doc binutils \
        git python3-pip python3-dev cmake gfortran build-essential \
        libblas3 libblas-dev liblapack3 liblapack-dev libatlas-base-dev \
        texlive texlive-latex-extra texlive-fonts-recommended dvipng cm-super \
        postgresql postgresql-client libpq-dev && \
    cd /usr/local/bin && \
    ln -s /usr/bin/python3 python && \
    pip3 --no-cache-dir install --upgrade pip && \
    useradd --create-home --shell /bin/bash nmma && \
    sed -i "s|local   all             postgres                                peer|local   all             postgres                                trust\nlocal   all             nmma                                trust|g" /etc/postgresql/12/main/pg_hba.conf

RUN service postgresql restart && createuser -U postgres nmma && createdb -U postgres nmma && psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE nmma TO nmma;"

# place to keep our app and the data:
RUN mkdir -p /app /data /data/logs /_tmp /app/nmma /app/nmma_db /app/priors /app/svdmodels

# copy over the config and the code
COPY ["docker.yaml", "config.yaml", "setup.py", "setup.cfg", "versioneer.py", "nmma_db/generate_supervisord_conf.py", "/app/"]
COPY ["nmma", "/app/nmma"]
COPY ["nmma_db", "/app/nmma_db"]
COPY ["priors", "/app/priors"]
COPY ["svdmodels", "/app/svdmodels"]

# change working directory to /app
WORKDIR /app/nmma

# Install MultiNest
RUN git clone https://github.com/JohannesBuchner/MultiNest && cd MultiNest/build && cmake .. && make && cd ../..
ENV LD_LIBRARY_PATH /usr/local/lib:/app/MultiNest/lib

RUN pip install .

# change working directory to /app
WORKDIR /app

RUN bash -c "cp docker.yaml config.yaml"

# install python libs and generate supervisord config file
RUN pip install . && \
    python generate_supervisord_conf.py api

USER nmma

# run container
#CMD exec /bin/bash -c "trap : TERM INT; sleep infinity & wait"
CMD python nmma_db/api.py
#CMD /usr/local/bin/supervisord -n -c supervisord_api.conf
#ENTRYPOINT ["/bin/bash"]

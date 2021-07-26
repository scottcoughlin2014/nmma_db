FROM python:3.7
#FROM python:3.7-slim

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends sudo apt-utils && \
    apt-get install -y --no-install-recommends \
        gcc libopenmpi-dev openmpi-bin openmpi-common openmpi-doc binutils \
        git sudo apt-utils

# place to keep our app and the data:
RUN mkdir -p /app /data /data/logs /_tmp /app/nmma /app/nmma_db /app/priors /app/svdmodels

# copy over the config and the code
COPY ["config.yaml", "setup.py", "setup.cfg", "versioneer.py", "nmma_db/generate_supervisord_conf.py", "/app/"]
COPY ["nmma", "/app/nmma"]
COPY ["nmma_db", "/app/nmma_db"]
COPY ["priors", "/app/priors"]
COPY ["svdmodels", "/app/svdmodels"]

# change working directory to /app
WORKDIR /app/nmma
RUN pip install .

# change working directory to /app
WORKDIR /app

# install python libs and generate supervisord config file
RUN pip install . && \
    python generate_supervisord_conf.py api

# run container
#CMD python api.py
#CMD /usr/local/bin/supervisord -n -c supervisord_api.conf
ENTRYPOINT ["/bin/bash"]

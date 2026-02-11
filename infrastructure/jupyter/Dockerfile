FROM jupyter/datascience-notebook:python-3.10

USER root

# Needed for PySpark + PyFlink (JVM-based).
RUN apt-get update \
  && apt-get install -y --no-install-recommends openjdk-11-jre-headless \
  && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
  && rm -f /tmp/requirements.txt

USER ${NB_UID}

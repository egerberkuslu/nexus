FROM tomcat:9.0-jdk17-temurin

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    curl \
    ca-certificates \
    procps \
  && rm -rf /var/lib/apt/lists/*

# Official Tomcat images keep the default apps (ROOT/docs/manager/host-manager)
# under webapps.dist; enable them so browsing "/" doesn't return 404.
RUN cp -a /usr/local/tomcat/webapps.dist/* /usr/local/tomcat/webapps/

EXPOSE 8080

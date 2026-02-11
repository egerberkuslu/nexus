FROM maven:3.9-eclipse-temurin-11 AS builder

WORKDIR /build
COPY pom.xml /build/pom.xml
COPY src/ /build/src/
RUN mvn -q -DskipTests package

FROM flink:1.18.1-scala_2.12-java11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

ARG FLINK_KAFKA_CONNECTOR_VERSION=3.2.0-1.18
RUN curl -fsSL "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${FLINK_KAFKA_CONNECTOR_VERSION}/flink-sql-connector-kafka-${FLINK_KAFKA_CONNECTOR_VERSION}.jar" \
  -o "/opt/flink/lib/flink-sql-connector-kafka-${FLINK_KAFKA_CONNECTOR_VERSION}.jar"

WORKDIR /opt/flink/jobs
COPY --from=builder /build/target/metrics-feature-job-1.0.0.jar /opt/flink/jobs/metrics-feature-job.jar
COPY submit-job.sh /opt/flink/jobs/submit-job.sh
RUN chmod +x /opt/flink/jobs/submit-job.sh

USER flink
ENTRYPOINT ["/opt/flink/jobs/submit-job.sh"]

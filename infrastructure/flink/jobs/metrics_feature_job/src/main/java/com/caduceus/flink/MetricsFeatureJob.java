package com.caduceus.flink;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.functions.KeySelector;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.api.common.serialization.SimpleStringSchema;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.HashMap;
import java.util.Map;

public class MetricsFeatureJob {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<Map<String, Object>>() {};

    private static final String DEFAULT_BOOTSTRAP = "kafka:9092";
    private static final String DEFAULT_RAW_TOPIC = "metrics.raw";
    private static final String DEFAULT_PROCESSED_TOPIC = "metrics.processed";

    public static void main(String[] args) throws Exception {
        Map<String, String> params = parseArgs(args);
        String bootstrap = params.getOrDefault("bootstrap.servers", DEFAULT_BOOTSTRAP);
        String rawTopic = params.getOrDefault("topic.raw", DEFAULT_RAW_TOPIC);
        String processedTopic = params.getOrDefault("topic.processed", DEFAULT_PROCESSED_TOPIC);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(10_000);

        KafkaSource<String> source = KafkaSource.<String>builder()
            .setBootstrapServers(bootstrap)
            .setTopics(rawTopic)
            .setGroupId("flink-metrics-feature-job")
            .setStartingOffsets(OffsetsInitializer.latest())
            .setValueOnlyDeserializer(new SimpleStringSchema())
            .build();

        DataStream<String> input = env.fromSource(source, WatermarkStrategy.noWatermarks(), "metrics.raw");

        DataStream<String> processed = input
            .keyBy(new EnvelopeKeySelector())
            .process(new FeatureProcessFunction());

        KafkaSink<String> sink = KafkaSink.<String>builder()
            .setBootstrapServers(bootstrap)
            .setRecordSerializer(
                KafkaRecordSerializationSchema.builder()
                    .setTopic(processedTopic)
                    .setValueSerializationSchema(new SimpleStringSchema())
                    .build()
            )
            .build();

        processed.sinkTo(sink);

        env.execute("metrics-feature-job");
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> out = new HashMap<>();
        if (args == null) return out;
        for (int i = 0; i < args.length; i++) {
            String raw = args[i];
            if (raw == null) continue;
            String token = raw.trim();
            if (!token.startsWith("--")) continue;
            token = token.substring(2);
            String key;
            String value;
            int eq = token.indexOf('=');
            if (eq >= 0) {
                key = token.substring(0, eq);
                value = token.substring(eq + 1);
            } else {
                key = token;
                value = (i + 1 < args.length) ? String.valueOf(args[i + 1]) : "";
                if (i + 1 < args.length) i++;
            }
            if (!key.isEmpty()) out.put(key, value);
        }
        return out;
    }

    private static class EnvelopeKeySelector implements KeySelector<String, String> {
        @Override
        public String getKey(String value) {
            try {
                Map<String, Object> envelope = MAPPER.readValue(value, MAP_TYPE);
                String topologyId = asString(envelope.get("topology_id"));
                String device = asString(envelope.get("device"));
                Object metricsObj = envelope.get("metrics");
                if ((topologyId == null || topologyId.isEmpty()) && metricsObj instanceof Map) {
                    topologyId = asString(((Map<?, ?>) metricsObj).get("topology_id"));
                }
                if ((device == null || device.isEmpty()) && metricsObj instanceof Map) {
                    device = asString(((Map<?, ?>) metricsObj).get("device"));
                }
                if (topologyId == null) topologyId = "";
                if (device == null) device = "";
                String key = topologyId + "|" + device;
                return key.isEmpty() ? "unknown" : key;
            } catch (Exception e) {
                return "unknown";
            }
        }
    }

    private static class FeatureProcessFunction extends KeyedProcessFunction<String, String, String> {
        private transient ValueState<Long> lastBytesSent;
        private transient ValueState<Long> lastBytesReceived;
        private transient ValueState<Long> lastDropsIn;
        private transient ValueState<Long> lastDropsOut;
        private transient ValueState<Long> lastTsMs;
        private transient ValueState<Double> cpuEwma;
        private transient ValueState<Double> memEwma;

        @Override
        public void open(Configuration parameters) {
            lastBytesSent = getRuntimeContext().getState(new ValueStateDescriptor<>("last_bytes_sent", Long.class));
            lastBytesReceived = getRuntimeContext().getState(new ValueStateDescriptor<>("last_bytes_received", Long.class));
            lastDropsIn = getRuntimeContext().getState(new ValueStateDescriptor<>("last_drops_in", Long.class));
            lastDropsOut = getRuntimeContext().getState(new ValueStateDescriptor<>("last_drops_out", Long.class));
            lastTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("last_ts_ms", Long.class));
            cpuEwma = getRuntimeContext().getState(new ValueStateDescriptor<>("cpu_ewma", Double.class));
            memEwma = getRuntimeContext().getState(new ValueStateDescriptor<>("mem_ewma", Double.class));
        }

        @Override
        public void processElement(String value, Context ctx, Collector<String> out) {
            try {
                Map<String, Object> envelope = MAPPER.readValue(value, MAP_TYPE);
                Map<String, Object> metrics = new HashMap<>();
                Object metricsObj = envelope.get("metrics");
                if (metricsObj instanceof Map) {
                    for (Map.Entry<?, ?> entry : ((Map<?, ?>) metricsObj).entrySet()) {
                        if (entry.getKey() != null) metrics.put(String.valueOf(entry.getKey()), entry.getValue());
                    }
                }

                long tsMs = parseTimestampMs(envelope.get("timestamp"));
                if (tsMs <= 0) tsMs = parseTimestampMs(metrics.get("timestamp"));
                if (tsMs <= 0) tsMs = System.currentTimeMillis();

                long curBytesSent = asLong(metrics.get("bytes_sent"));
                long curBytesRecv = asLong(metrics.get("bytes_received"));
                long curDropsIn = asLong(metrics.get("drops_in"));
                long curDropsOut = asLong(metrics.get("drops_out"));
                double curCpu = asDouble(metrics.get("cpu_percent"));
                double curMem = asDouble(metrics.get("memory_percent"));

                Long prevTs = lastTsMs.value();
                Long prevSent = lastBytesSent.value();
                Long prevRecv = lastBytesReceived.value();
                Long prevDropsIn = lastDropsIn.value();
                Long prevDropsOut = lastDropsOut.value();

                double dtSec = 0.0;
                if (prevTs != null && prevTs > 0 && tsMs > prevTs) {
                    dtSec = (tsMs - prevTs) / 1000.0;
                }
                if (dtSec <= 0.0) dtSec = 5.0;

                long deltaSent = (prevSent == null) ? 0L : Math.max(0L, curBytesSent - prevSent);
                long deltaRecv = (prevRecv == null) ? 0L : Math.max(0L, curBytesRecv - prevRecv);
                long deltaDrops = (prevDropsIn == null || prevDropsOut == null)
                    ? 0L
                    : Math.max(0L, (curDropsIn - prevDropsIn) + (curDropsOut - prevDropsOut));

                double txBps = deltaSent / dtSec;
                double rxBps = deltaRecv / dtSec;
                double dropsRate = deltaDrops / dtSec;

                double alpha = 0.2;
                Double prevCpuEwma = cpuEwma.value();
                Double prevMemEwma = memEwma.value();
                double nextCpuEwma = prevCpuEwma == null ? curCpu : (alpha * curCpu + (1 - alpha) * prevCpuEwma);
                double nextMemEwma = prevMemEwma == null ? curMem : (alpha * curMem + (1 - alpha) * prevMemEwma);

                Map<String, Object> features = new HashMap<>();
                features.put("tx_bytes_delta", deltaSent);
                features.put("rx_bytes_delta", deltaRecv);
                features.put("tx_bps", txBps);
                features.put("rx_bps", rxBps);
                features.put("drops_delta", deltaDrops);
                features.put("drops_rate", dropsRate);
                features.put("cpu_ewma", nextCpuEwma);
                features.put("memory_ewma", nextMemEwma);

                // Promote computed features into the metrics map so downstream sinks (e.g. Kafka Connect -> InfluxDB)
                // can store both raw + processed streams using a single ExtractField("metrics") transform.
                // Also update the per-record source so Influx tags can distinguish "grpc" vs "flink.features".
                try {
                    metrics.put("source", "flink.features");
                    metrics.put("timestamp", tsMs);
                    for (Map.Entry<String, Object> e : features.entrySet()) {
                        metrics.put(e.getKey(), e.getValue());
                    }
                } catch (Exception ignored) {
                }

                Map<String, Object> outEnvelope = new HashMap<>(envelope);
                outEnvelope.put("source", "flink.features");
                outEnvelope.put("timestamp", toIso(tsMs));
                outEnvelope.put("metrics", metrics);
                outEnvelope.put("features", features);

                out.collect(MAPPER.writeValueAsString(outEnvelope));

                lastTsMs.update(tsMs);
                lastBytesSent.update(curBytesSent);
                lastBytesReceived.update(curBytesRecv);
                lastDropsIn.update(curDropsIn);
                lastDropsOut.update(curDropsOut);
                cpuEwma.update(nextCpuEwma);
                memEwma.update(nextMemEwma);
            } catch (Exception e) {
                // Drop malformed messages
            }
        }
    }

    private static long parseTimestampMs(Object tsObj) {
        if (tsObj == null) return 0L;
        if (tsObj instanceof Number) return ((Number) tsObj).longValue();
        String s = asString(tsObj);
        if (s == null || s.isEmpty()) return 0L;
        String t = s.trim();
        try {
            if (t.endsWith("Z") || t.contains("+")) {
                return Instant.parse(t).toEpochMilli();
            }
        } catch (Exception ignored) {
        }
        try {
            return LocalDateTime.parse(t).toInstant(ZoneOffset.UTC).toEpochMilli();
        } catch (Exception ignored) {
        }
        return 0L;
    }

    private static String toIso(long tsMs) {
        try {
            return Instant.ofEpochMilli(tsMs).toString();
        } catch (Exception e) {
            return Instant.now().toString();
        }
    }

    private static String asString(Object value) {
        if (value == null) return null;
        return String.valueOf(value);
    }

    private static long asLong(Object value) {
        if (value == null) return 0L;
        if (value instanceof Number) return ((Number) value).longValue();
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception e) {
            return 0L;
        }
    }

    private static double asDouble(Object value) {
        if (value == null) return 0.0;
        if (value instanceof Number) return ((Number) value).doubleValue();
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (Exception e) {
            return 0.0;
        }
    }
}

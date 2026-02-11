# Caduceus-Flux Sistem Mimarisi

## Amac ve Kapsam
Caduceus-Flux, Mininet/Containernet/Mininet-WiFi tabanli emulasyon cekirdegi uzerine insa edilmis, mikroservis odakli bir ag deney platformudur. Hedef; topoloji tasarimi, emulasyon calistirma, runtime degisiklik, gozlemlenebilirlik, snapshot/restore, P4 veri duzlemi ve AI/LLM kontrollu otomasyon gibi yetenekleri tek bir platformda birlestirmektir.

Bu dokuman, sistemin nasil calistigini ve servislerin birbirine nasil baglandigini detayli sekilde aciklar. Daha ayrintili servis aciklamalari icin `docs/microservices/` altindaki dosyalara bakiniz.

## Tasarim Hedefleri
- **Modulerlik:** Her fonksiyonun bagimsiz mikroservise ayrilmasi.
- **Coklu Topoloji:** Ayn anda birden fazla topolojinin calistirilabilmesi.
- **Izolasyon:** Topoloji bazli altyapi ayristirma ve kaynak sinirlama.
- **Gozlemlenebilirlik:** Metrik, log ve olay akisi ile uctan uca takip.
- **Tekrarlanabilirlik:** Snapshot/restore ile deneylerin geri alinabilmesi.
- **Otomasyon:** Test, config planlama ve AI destekli kontrol.
- **Guvenlik:** MCP policy ve read-only proxy ile risk azaltma.

## Katmanli Mimari (Ustten Alta)
1. **Arayuz Katmani (UI):** React tabanli web arayuzu; editor, monitoring, AI console ve data lab gibi moduller.
2. **API Gateway:** MCP Server tekil API giris noktasi; mikroservislere route eder.
3. **Kontrol Duzlemi Mikroservisleri:** Topoloji, Orchestrator, Device/Protocol/Controller, Snapshot, Monitoring, AI/LLM, MANO vb.
4. **Emulasyon Runtime:** Her topoloji icin ayrik emulasyon container'i; gRPC ile kontrol edilir.
5. **Veri/Mesaj Katmani:** PostgreSQL, MongoDB, Redis, InfluxDB/Prometheus, RabbitMQ ve Kafka.
6. **Opsiyonel Izole Altyapi:** Topoloji bazli InfluxDB/Grafana/Consul/RabbitMQ/Kafka/Zookeeper/Portainer stack'leri.

## Bilesen Gruplari ve Sorumluluklar
### Topoloji ve Orkestrasyon
- **Topology Service:** Proje/topoloji CRUD, staged apply, canli editor guncellemeleri.
- **Orchestrator:** Emulasyon baslatma/durdurma, runtime port atama, izolasyon altyapisi, test kosucular.

### Runtime Operasyonlari
- **Device Manager:** Calisan emulasyonda cihaz ekleme/silme/guncelleme.
- **Protocol Manager:** Protokol pluginleri ve hot-swap.
- **Controller Manager:** SDN controller lifecycle (osken, ryu, onos, opendaylight, pox, custom).
- **Webshell:** Mininet CLI ve namespace komut calistirma.

### Gozlemlenebilirlik ve Analitik
- **Monitoring Service:** gRPC metrik alma, InfluxDB yazma, Prometheus export.
- **Metrics Collector:** gRPC -> Kafka metrik bridge.
- **Decision Engine:** Kafka uzerinden akisan metriklerden karar/alert uretimi.

### AI/LLM ve MCP
- **AI Gateway:** LLM provider gateway, MCP request generate/execute, audit log.
- **MCP Tool Hub:** Registry ve guvenli proxy (read-only, allow/deny path).
- **MCP Proxy:** Genel amacli proxy shim.

### NFV/MANO
- **MANO Service:** Yerel VNF/NS lifecycle.
- **OSM Connector:** ETSI OSM NBI adaptor/proxy.
- **VIM Emulator:** OpenStack benzeri API (VIM).

### P4 Veri Duzlemi
- **P4 Manager:** P4 compile ve BMv2 switch yonetimi.

## Servisler Arasi Entegrasyon Haritasi
### 1) Topoloji -> Emulasyon
- Topology Service topoloji verisini saklar.
- Orchestrator topoloji bilgisi alir ve emulasyon container'i baslatir.
- Runtime gRPC uzerinden cihaz/link konfiglerini uygular.

### 2) Runtime Degisiklikler
- Device Manager runtime cihaz degisikligi yapar.
- Protocol Manager protokol hot-swap uygular.
- Controller Manager controller yaratir/kaydeder, Device Manager switch controller baglar.

### 3) Gozlemlenebilirlik Akisi
- Runtime -> Monitoring Service (gRPC) -> InfluxDB/Prometheus.
- Runtime -> Metrics Collector (gRPC) -> Kafka -> Decision Engine.

### 4) Snapshot/Restore
- Snapshot Service planli veya manuel snapshot alir.
- Orchestrator runtime checkpoint/restore islerini koordine eder.

### 5) AI/LLM Kontrol
- AI Console uzerinden dogal dil komutu.
- AI Gateway MCP istekleri uretir.
- MCP Tool Hub proxy uzerinden mikroservis cagrilari yapar.

### 6) NFV/MANO
- MANO Service VNF/NS lifecycle islerini yurutur.
- OSM Connector ETSI OSM entegrasyonu saglar.
- VIM Emulator OSM icin VIM API sunar.

## Izolasyon ve Coklu Topoloji Modeli
- **Shared Mod:** Tum topolojiler ortak altyapi servislerini kullanir.
- **Isolated Mod:** Her topoloji icin ayri InfluxDB/Grafana/Consul/RabbitMQ/Kafka/Portainer stack'i olusur.
- **Adlandirma:** Topoloji bazli prefix ile container/volume/network olusturulur.
- **Port Ayrimi:** Izole modda belirli port araliklari kullanilir.
- **Eszamanlilik:** Orchestrator topoloji bazli kilitlerle cakismayi azaltir.

## UI Modulleri ve Detayli Yetkinlikler
### Features (/features)
- Platformun yeteneklerini ozetleyen landing sayfasi.
- Kullaniciya mimari ozellik setlerini hizli anlatim.

### Projects (/projects)
- Proje listesi ve proje bazli topoloji yonetimi.
- Yeni proje olusturma, mevcut projeleri listeleme.

### Topology Editor (/topology/:id)
- Drag-drop topoloji editoru.
- Node/link duzenleme, metadata ayarlari.
- Staged degisiklik -> apply akisi.

### Monitoring (/monitoring/:id)
- Canli metrik goruntuleme.
- Zaman serisi ve device bazli metrik analizi.

### Network Manager (/network-manager)
- Cihaz envanteri, protokol ve controller ayarlari.
- Test kosuculari (ping/iperf/CPU/mem).
- Terminal/CLI ve diagnostik arayuzleri.

### Snapshots (/snapshots, /schedules)
- Snapshot listeleri, detaylari ve restore.
- Snapshot schedule planlama ve takvim.

### AI Console (/ai-console)
- Chatbot benzeri LLM kontrolu.
- Dogal dil ile topoloji yonetimi ve otomasyon.

### AI Settings / ML Models
- LLM provider konfigleri ve model secimi.
- Decision Engine tarafindaki model/algoritma profilleri.

### Data Lab (/data-lab)
- JupyterLab tabanli analiz ortami.
- Metrik ve loglar uzerinde offline analiz.

### API Docs (/docs)
- MCP Gateway uzerinden OpenAPI dokumantasyonu.

## UI Proxy Mekanizmalari (Same-Origin)
Frontend Nginx, farkli servis UI'larini ayni origin altinda gostermek icin proxy kurallari saglar:
- **/infra-proxy/portainer/**: Topoloji bazli Portainer UI
- **/infra-proxy/kafka-ui/**: Topoloji bazli Kafka UI
- **/infra-proxy/kafka-ui-shared/**: Paylasimli Kafka UI
- **/infra-proxy/controllers/**: Controller UI'lari (ONOS dahil)
- **/infra-proxy/osm-ng-ui/** ve **/infra-proxy/osm-light-ui/**: ETSI OSM arayuzleri
- **/infra-proxy/flink-shared/**, **/infra-proxy/spark-shared/**, **/infra-proxy/hdfs-shared/**
- **/infra-proxy/hive-shared/**, **/infra-proxy/pgadmin-shared/**, **/infra-proxy/mongo-express-shared/**, **/infra-proxy/hue-shared/**
- **/jupyter/**: JupyterLab ayni-origin proxy

Bu mekanizma ile Kafka UI, ONOS UI ve benzeri arayuzler UI icinden embed edilerek goruntulenebilir.

## Veri ve Mesaj Katmani
- **PostgreSQL:** Topoloji/proje, MANO ve AI kayitlari.
- **MongoDB:** Snapshot metadata ve buyuk kayitlar.
- **Redis:** Runtime state ve oturumlar.
- **InfluxDB:** Metrik depolama.
- **Prometheus:** Scrape ve metrik export.
- **RabbitMQ:** Olay tabanli servis iletisimi.
- **Kafka:** Streaming pipeline ve alert akisi.

## Dagitim ve Calistirma Mimarisi
- **docker-compose:** Tum servisler tek host uzerinde calisacak sekilde tanimlidir.
- **Emulasyon runtime:** Privileged container; gRPC portlari dinamik atanir.
- **Opsiyonel analytic stack:** Kafka/Flink/Spark/HDFS/Hive/Hue gibi servisler birlikte calistirilabilir.
- **Izole mod:** Orchestrator topolojiye ozel stack'i otomatik ayaga kaldirir.

## Mimari Diyagram (Mermaid)
```mermaid
flowchart TB
  UI[Web UI] -->|REST/WS| MCP[MCP Server API Gateway]
  MCP --> Topology[Topology Service]
  MCP --> Orchestrator[Orchestrator]
  MCP --> DeviceMgr[Device Manager]
  MCP --> ProtocolMgr[Protocol Manager]
  MCP --> ControllerMgr[Controller Manager]
  MCP --> Snapshot[Snapshot Service]
  MCP --> Monitoring[Monitoring Service]
  MCP --> Metrics[Metrics Collector]
  MCP --> Decision[Decision Engine]
  MCP --> P4[P4 Manager]
  MCP --> MANO[MANO Service]
  MCP --> OSM[OSM Connector]
  MCP --> VIM[VIM Emulator]
  MCP --> AIGW[AI Gateway]
  AIGW --> MCPHub[MCP Tool Hub]
  Orchestrator --> Runtime[Emulation Container (gRPC)]
  Monitoring --> InfluxDB[(InfluxDB)]
  Metrics --> Kafka[(Kafka)] --> Decision
  Topology --> Postgres[(PostgreSQL)]
  DeviceMgr --> Postgres
  Snapshot --> Mongo[(MongoDB)]
  Orchestrator --> Redis[(Redis)]
  Orchestrator --> Consul[(Consul)]
  Orchestrator --> Rabbit[(RabbitMQ)]
```

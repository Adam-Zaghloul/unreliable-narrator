// Player badge (ESP32-C3). NOT YET COMPILED OR BENCH-TESTED.
// Toolchain: Arduino-ESP32 core 3.x + NimBLE-Arduino 2.x.
//
// Every 2 s it sends one ESP-NOW broadcast to the gateway with:
//   its id, a sequence number, which buttons were pressed since the last packet,
//   and the MEDIAN RSSI of every beacon/badge it heard in those 2 s.
// It also advertises itself over BLE so other badges can hear it (used later, not for truth).
// The gateway can tell it to buzz (a "witness ping").
//
// Timestamps: the hub stamps packets on arrival, so badges need no clock sync.

#include <NimBLEDevice.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#define BADGE_ID 1          // CHANGE PER BADGE (1..254)
#define ESPNOW_CHANNEL 1
const int PIN_TRUE = 2;     // button to GND, internal pull-up
const int PIN_LIE = 3;      // button to GND, internal pull-up
const int PIN_MOTOR = 4;    // 2N7000 gate -> coin vibration motor (with flyback diode)
const uint32_t PERIOD_MS = 2000;

// ---- shared protocol (keep identical in badge, beacon and gateway) ----
// BLE manufacturer data: FF FF 'U' 'N' kind id   (0xFFFF = test company id)
enum : uint8_t { KIND_BEACON = 'B', KIND_BADGE = 'P' };
struct __attribute__((packed)) Peer { uint8_t kind; uint8_t id; int8_t rssi; };
struct __attribute__((packed)) Packet {
  uint8_t magic[2];  // 'U','N'
  uint8_t badge_id;
  uint16_t seq;
  uint8_t buttons;   // bit0 TRUE pressed, bit1 LIE pressed (since last packet)
  uint8_t n;
  Peer peers[16];
};
struct __attribute__((packed)) Command { uint8_t magic[2]; uint8_t target; uint8_t cmd; uint16_t ms; };  // cmd 1 = buzz
// ----------------------------------------------------------------------

const uint8_t BCAST_ADDR[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
const int MAX_PEERS = 16, MAX_SAMPLES = 8;

struct Samples { uint8_t kind, id, count; int8_t rssi[MAX_SAMPLES]; };
Samples table[MAX_PEERS];
int tableSize = 0;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;  // scan callback runs in another task

volatile uint8_t buttonsLatched = 0;
volatile uint32_t buzzUntil = 0;
uint16_t seq = 0;
uint32_t lastSend = 0;

void addSample(uint8_t kind, uint8_t id, int rssi) {
  portENTER_CRITICAL(&mux);
  int i = 0;
  while (i < tableSize && !(table[i].kind == kind && table[i].id == id)) i++;
  if (i == tableSize && tableSize < MAX_PEERS) {
    table[i] = {kind, id, 0, {0}};
    tableSize++;
  }
  if (i < tableSize && table[i].count < MAX_SAMPLES) table[i].rssi[table[i].count++] = (int8_t)rssi;
  portEXIT_CRITICAL(&mux);
}

int8_t medianOf(int8_t* v, uint8_t n) {  // n <= 8, insertion sort is fine
  for (uint8_t i = 1; i < n; i++) {
    int8_t x = v[i]; int j = i - 1;
    while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
    v[j + 1] = x;
  }
  return v[n / 2];
}

class ScanCB : public NimBLEScanCallbacks {
  void onResult(const NimBLEAdvertisedDevice* d) override {
    std::string m = d->getManufacturerData();
    if (m.size() < 6) return;
    if ((uint8_t)m[0] != 0xFF || (uint8_t)m[1] != 0xFF || m[2] != 'U' || m[3] != 'N') return;
    addSample((uint8_t)m[4], (uint8_t)m[5], d->getRSSI());
  }
} scanCB;

void onRecv(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
  if (len != sizeof(Command)) return;
  const Command* c = (const Command*)data;
  if (c->magic[0] != 'U' || c->magic[1] != 'N') return;
  if (c->target != BADGE_ID && c->target != 0xFF) return;
  if (c->cmd == 1) buzzUntil = millis() + c->ms;
}

// Core 4.x builds NimBLE with extended advertising on, which swaps the advertising API.
// This helper sends a plain legacy, non-connectable advert either way.
void startAdvertising(const std::string& md, uint16_t minUnits, uint16_t maxUnits) {
#if CONFIG_BT_NIMBLE_EXT_ADV
  NimBLEExtAdvertisement ad;
  ad.setLegacyAdvertising(true);
  ad.setConnectable(false);
  ad.setScannable(false);
  ad.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  ad.setManufacturerData(md);
  ad.setMinInterval(minUnits);
  ad.setMaxInterval(maxUnits);
  NimBLEExtAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setInstanceData(0, ad);
  adv->start(0);
#else
  NimBLEAdvertisementData ad;
  ad.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  ad.setManufacturerData(md);
  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setAdvertisementData(ad);
  adv->setMinInterval(minUnits);
  adv->setMaxInterval(maxUnits);
  adv->start();
#endif
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRUE, INPUT_PULLUP);
  pinMode(PIN_LIE, INPUT_PULLUP);
  pinMode(PIN_MOTOR, OUTPUT);

  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK) { Serial.println("esp_now_init failed"); }
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BCAST_ADDR, 6);
  peer.channel = ESPNOW_CHANNEL;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
  esp_now_register_recv_cb(onRecv);

  NimBLEDevice::init("");
  startAdvertising(std::string{(char)0xFF, (char)0xFF, 'U', 'N', (char)KIND_BADGE, (char)BADGE_ID}, 320, 352);  // ~200 ms

  NimBLEScan* scan = NimBLEDevice::getScan();
  scan->setScanCallbacks(&scanCB, true);  // true = report every advertisement, not just new devices
  scan->setActiveScan(false);              // passive: we only need RSSI + manufacturer data
  scan->setInterval(100);
  scan->setWindow(60);                     // leave radio time for ESP-NOW
  scan->setMaxResults(0);                  // don't store results, callbacks only
  scan->start(0, false, true);             // 0 = scan forever
}

void loop() {
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll >= 20) {  // 20 ms polling acts as debounce
    lastPoll = millis();
    if (digitalRead(PIN_TRUE) == LOW) buttonsLatched |= 1;
    if (digitalRead(PIN_LIE) == LOW) buttonsLatched |= 2;
  }
  digitalWrite(PIN_MOTOR, (int32_t)(buzzUntil - millis()) > 0 ? HIGH : LOW);

  if (millis() - lastSend < PERIOD_MS) return;
  lastSend = millis();

  Packet pkt = {};
  pkt.magic[0] = 'U'; pkt.magic[1] = 'N';
  pkt.badge_id = BADGE_ID;
  pkt.seq = seq++;
  pkt.buttons = buttonsLatched;
  buttonsLatched = 0;

  Samples snap[MAX_PEERS];
  int n;
  portENTER_CRITICAL(&mux);
  n = tableSize;
  memcpy(snap, table, sizeof(Samples) * n);
  tableSize = 0;
  portEXIT_CRITICAL(&mux);

  for (int i = 0; i < n && pkt.n < 16; i++) {
    if (snap[i].count == 0) continue;
    pkt.peers[pkt.n++] = {snap[i].kind, snap[i].id, medianOf(snap[i].rssi, snap[i].count)};
  }
  esp_now_send(BCAST_ADDR, (uint8_t*)&pkt, 7 + pkt.n * sizeof(Peer));
}

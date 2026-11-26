// Gateway (ESP32-C3 on USB). NOT YET COMPILED OR BENCH-TESTED. Arduino-ESP32 core 3.x.
//
// Badge packets in (ESP-NOW) -> one JSON line per packet out (USB serial, 115200):
//   {"badge":1,"seq":42,"buttons":0,"peers":[["B",1,-57],["P",3,-70]]}
// Commands in (serial) -> ESP-NOW broadcast out:
//   BUZZ <badge_id> <ms>     e.g. "BUZZ 3 400"   (badge_id 255 = all badges)

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#define ESPNOW_CHANNEL 1

// ---- shared protocol (keep identical in badge, beacon and gateway) ----
struct __attribute__((packed)) Peer { uint8_t kind; uint8_t id; int8_t rssi; };
struct __attribute__((packed)) Packet {
  uint8_t magic[2]; uint8_t badge_id; uint16_t seq; uint8_t buttons; uint8_t n; Peer peers[16];
};
struct __attribute__((packed)) Command { uint8_t magic[2]; uint8_t target; uint8_t cmd; uint16_t ms; };
// ----------------------------------------------------------------------

const uint8_t BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
QueueHandle_t queue;  // receive callback runs in the Wi-Fi task: copy out, print in loop()

void onRecv(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
  if (len < 7 || len > (int)sizeof(Packet)) return;
  Packet p = {};
  memcpy(&p, data, len);
  if (p.magic[0] != 'U' || p.magic[1] != 'N') return;
  if (7 + p.n * (int)sizeof(Peer) != len) return;  // malformed
  xQueueSend(queue, &p, 0);
}

void setup() {
  Serial.begin(115200);
  queue = xQueueCreate(32, sizeof(Packet));
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_now_init();
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST, 6);
  peer.channel = ESPNOW_CHANNEL;
  esp_now_add_peer(&peer);
  esp_now_register_recv_cb(onRecv);
  Serial.println("{\"gateway\":\"ready\"}");
}

void handleCommand(String line) {
  int target, ms;
  if (sscanf(line.c_str(), "BUZZ %d %d", &target, &ms) == 2) {
    Command c = {{'U', 'N'}, (uint8_t)target, 1, (uint16_t)ms};
    esp_now_send(BROADCAST, (uint8_t*)&c, sizeof(c));
  }
}

void loop() {
  Packet p;
  while (xQueueReceive(queue, &p, 0) == pdTRUE) {
    Serial.printf("{\"badge\":%u,\"seq\":%u,\"buttons\":%u,\"peers\":[", p.badge_id, p.seq, p.buttons);
    for (int i = 0; i < p.n; i++) {
      Serial.printf("%s[\"%c\",%u,%d]", i ? "," : "", p.peers[i].kind, p.peers[i].id, p.peers[i].rssi);
    }
    Serial.println("]}");
  }
  if (Serial.available()) handleCommand(Serial.readStringUntil('\n'));
}

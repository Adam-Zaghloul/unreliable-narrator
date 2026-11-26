// Zone beacon (ESP32-C3). One per room or landmark. Advertise-only.
// NOT YET COMPILED OR BENCH-TESTED. Toolchain: Arduino-ESP32 core 3.x + NimBLE-Arduino 2.x.
//
// Manufacturer data: FF FF 'U' 'N' 'B' ZONE_ID. The hub maps ZONE_ID -> room name.
// Tip: mount every beacon at the same height and away from metal, and keep TX power equal,
// otherwise one room "wins" the RSSI comparison by default.

#include <NimBLEDevice.h>

#define ZONE_ID 1  // CHANGE PER BEACON (1..254)

void setup() {
  NimBLEDevice::init("");
  NimBLEAdvertisementData ad;
  ad.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  std::string md = {(char)0xFF, (char)0xFF, 'U', 'N', 'B', (char)ZONE_ID};
  ad.setManufacturerData(md);
  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setAdvertisementData(ad);
  adv->setMinInterval(160);  // 160 * 0.625 ms = 100 ms
  adv->setMaxInterval(176);  // 110 ms; a little jitter avoids repeated collisions
  adv->start();
}

void loop() { delay(1000); }

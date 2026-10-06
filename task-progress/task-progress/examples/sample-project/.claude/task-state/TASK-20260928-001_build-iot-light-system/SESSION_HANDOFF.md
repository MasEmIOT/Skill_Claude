# Session Handoff — TASK-20260928-001

> Updated: 2026-09-28T04:02:45+00:00 · Latest checkpoint: checkpoint-003

## Which task?

TASK-20260928-001 — Build IoT Light System (project: Smart Home IoT)

## What was the goal?

Control a light remotely via ESP32 relay + Firebase RTDB

## What has been completed?


Project builds (T-001); WiFi reconnect verified on hardware (T-002).

## What is currently being worked on?


Relay driver written (src/relay.cpp) but never flashed — treat as ATTEMPTED.

## What files matter?


src/main.cpp (WiFi + main loop), src/relay.cpp (GPIO26 driver), platformio.ini.

## What decisions matter?


D-001 Firebase RTDB (not MQTT/polling) — do not switch without a new decision.

## What failed?


F-001 upload while serial monitor open → port busy. Close monitor first.

## What blockers exist?


B-001 WAITING_USER: enable Firebase Email/Password auth + device user.

## What has been tested?


T-001 build PASS, T-002 WiFi reconnect PASS. Relay untested.

## What must the next session do first?


Flash firmware and test relaySet() on GPIO26 locally (no Firebase needed), verify active-HIGH assumption. Then check whether user resolved B-001.

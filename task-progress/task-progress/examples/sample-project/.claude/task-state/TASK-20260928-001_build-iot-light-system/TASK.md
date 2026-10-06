# Task

Task ID: TASK-20260928-001
Task Name: Build IoT Light System
Task Slug: build-iot-light-system
Project: Smart Home IoT
Created: 2026-09-28T04:02:45+00:00
Last Updated: 2026-09-28T04:03:17+00:00
Status: IN_PROGRESS

## Objective

Control a light remotely via ESP32 relay + Firebase RTDB

## Requirements

- ESP32 connects to WiFi and reconnects automatically
- Relay state mirrors Firebase /light/state

## Constraints

- ESP32 DevKit v1, Arduino framework (PlatformIO)

## Acceptance Criteria

<!-- One checkbox per criterion. Tick [x] only with evidence, e.g. "- [x] Relay toggles remotely — evidence: T-004" -->
- [ ] WiFi reconnects after AP reboot
- [ ] Relay follows Firebase within 1 s

## Requirement Change Log

- 2026-09-28T04:02:45+00:00 — Task created.

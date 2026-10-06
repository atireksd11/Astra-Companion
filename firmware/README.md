# firmware

empty on purpose. pcb first.

later: platformio, esp32-s3, dual core.

- core 0: mpu6050 @ 100-200Hz, pid, drv8833 pwm. this one never waits on wifi.
- core 1: wifi, inmp441 -> stt, llm, tts -> max98357a, gc9a01 eyes

pin numbers: `docs/PINOUT.md`. if firmware and the pcb disagree, the pcb wins and firmware gets fixed.

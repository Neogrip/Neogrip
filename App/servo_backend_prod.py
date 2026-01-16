def us_to_duty(pulse_us: int, freq_hz: int) -> int:
    period_us = 1_000_000.0 / float(freq_hz)
    return int(round((pulse_us / period_us) * 65535))


class PCA9685Backend:
    def __init__(self, frequency_hz: int):
        import busio
        from board import SCL, SDA
        from adafruit_pca9685 import PCA9685

        self.frequency_hz = frequency_hz
        i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = frequency_hz

    def set_us(self, channel: int, pulse_us: int) -> None:
        self.pca.channels[channel].duty_cycle = us_to_duty(pulse_us, self.frequency_hz)

    def deinit(self) -> None:
        self.pca.deinit()
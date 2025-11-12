class PIDController:
    def __init__(
        self, kp: float, ki: float, kd: float, output_limits: tuple[float, float]
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0
        self.prev_error = 0
        self.output_limits = output_limits

    def update(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt if dt > 0 else 0
        self.prev_error = error

        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        output = max(min(output, self.output_limits[1]), self.output_limits[0])
        return output

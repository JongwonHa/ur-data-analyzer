# config/robot_specs.py
# UR 로봇 모델별 사양

ROBOT_SPECS = {
    "UR3e": {
        "max_payload": 3.0,
        "max_reach": 500,
        "max_joint_speed": [180, 180, 180, 360, 360, 360],
        "max_joint_accel": 800,
        "max_tcp_speed": 1.0,
        "nominal_current": [2.0, 2.0, 1.5, 1.0, 1.0, 1.0],
        "max_temp": 85,
        "weight": 11.2
    },
    "UR5e": {
        "max_payload": 5.0,
        "max_reach": 850,
        "max_joint_speed": [180, 180, 180, 360, 360, 360],
        "max_joint_accel": 800,
        "max_tcp_speed": 1.0,
        "nominal_current": [2.5, 2.5, 2.0, 1.5, 1.5, 1.5],
        "max_temp": 85,
        "weight": 20.6
    },
    "UR10e": {
        "max_payload": 12.5,
        "max_reach": 1300,
        "max_joint_speed": [120, 120, 180, 360, 360, 360],
        "max_joint_accel": 600,
        "max_tcp_speed": 1.0,
        "nominal_current": [3.5, 3.5, 3.0, 2.0, 2.0, 2.0],
        "max_temp": 85,
        "weight": 33.5
    },
    "UR16e": {
        "max_payload": 16.0,
        "max_reach": 900,
        "max_joint_speed": [120, 120, 180, 360, 360, 360],
        "max_joint_accel": 600,
        "max_tcp_speed": 1.0,
        "nominal_current": [4.0, 4.0, 3.5, 2.5, 2.5, 2.5],
        "max_temp": 85,
        "weight": 33.1
    },
    "UR20": {
        "max_payload": 20.0,
        "max_reach": 1750,
        "max_joint_speed": [120, 120, 180, 360, 360, 360],
        "max_joint_accel": 500,
        "max_tcp_speed": 2.0,
        "nominal_current": [5.0, 5.0, 4.0, 3.0, 3.0, 3.0],
        "max_temp": 85,
        "weight": 64.0
    },
    "UR30": {
        "max_payload": 30.0,
        "max_reach": 1300,
        "max_joint_speed": [120, 120, 180, 360, 360, 360],
        "max_joint_accel": 400,
        "max_tcp_speed": 2.0,
        "nominal_current": [6.0, 6.0, 5.0, 3.5, 3.5, 3.5],
        "max_temp": 85,
        "weight": 63.5
    }
}

SAFETY_MARGINS = {
    "speed": 0.85,
    "accel": 0.80,
    "current": 0.75,
    "temp": 0.90,
    "payload": 0.90
}

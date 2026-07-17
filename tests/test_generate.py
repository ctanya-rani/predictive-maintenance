import numpy as np
import pandas as pd
import pytest

from trainwatch.config import DAYS, SAMPLE_MINUTES, SENSORS, TRAIN_IDS
from trainwatch.generate import SAMPLES_PER_DAY, generate_fleet_data

END = pd.Timestamp("2026-07-17 00:00:00")


@pytest.fixture(scope="module")
def data():
    return generate_fleet_data(end=END)


def test_shape_and_columns(data):
    assert list(data.columns) == ["timestamp", "train_id", "sensor", "value"]
    expected = len(TRAIN_IDS) * len(SENSORS) * DAYS * SAMPLES_PER_DAY
    assert len(data) == expected


def test_cadence(data):
    channel = data[(data["train_id"] == "T-101") & (data["sensor"] == "brake_pressure_bar")]
    deltas = channel["timestamp"].diff().dropna().unique()
    assert len(deltas) == 1
    assert deltas[0] == pd.Timedelta(minutes=SAMPLE_MINUTES)


def test_deterministic_with_seed():
    a = generate_fleet_data(days=2, seed=7, end=END)
    b = generate_fleet_data(days=2, seed=7, end=END)
    pd.testing.assert_frame_equal(a, b)


def test_healthy_train_stays_near_baseline(data):
    channel = data[(data["train_id"] == "T-101") & (data["sensor"] == "axle_bearing_temp_c")]
    spec = SENSORS["axle_bearing_temp_c"]
    assert channel["value"].max() < spec.warn_high
    assert abs(channel["value"].median() - spec.baseline) < 8.0


def test_bearing_fault_ramps_up(data):
    channel = data[(data["train_id"] == "T-103") & (data["sensor"] == "axle_bearing_temp_c")]
    first_week = channel.head(7 * SAMPLES_PER_DAY)["value"].mean()
    last_day = channel.tail(SAMPLES_PER_DAY)["value"].mean()
    assert last_day > first_week + 20


def test_brake_leak_decays(data):
    channel = data[(data["train_id"] == "T-102") & (data["sensor"] == "brake_pressure_bar")]
    assert channel.tail(SAMPLES_PER_DAY)["value"].mean() < 7.8


def test_stuck_sensor_flatlines(data):
    channel = data[(data["train_id"] == "T-107") & (data["sensor"] == "traction_motor_current_a")]
    tail = channel.tail(SAMPLES_PER_DAY)["value"]
    assert np.allclose(tail, tail.iloc[0])

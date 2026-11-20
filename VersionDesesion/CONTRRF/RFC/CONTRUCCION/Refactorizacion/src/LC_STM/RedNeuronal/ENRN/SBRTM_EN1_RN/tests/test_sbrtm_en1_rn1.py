import pytest

from sbrtm_EN1_RN1 import NeuronaEntradaBase


def test_ring_buffer_respects_capacity():
    buffer = NeuronaEntradaBase.RingBuffer(3)

    for value in range(5):
        buffer.append(value)

    assert buffer.to_list() == [2, 3, 4]
    assert len(buffer) == 3


def test_ring_buffer_rejects_zero_capacity():
    with pytest.raises(ValueError):
        NeuronaEntradaBase.RingBuffer(0)


def test_ring_buffer_rejects_negative_capacity():
    with pytest.raises(ValueError):
        NeuronaEntradaBase.RingBuffer(-1)


def test_ring_buffer_rejects_non_integer_capacity():
    with pytest.raises(TypeError):
        NeuronaEntradaBase.RingBuffer(2.5)


def test_ring_buffer_clear():
    buffer = NeuronaEntradaBase.RingBuffer(3)
    buffer.append("sample")

    buffer.clear()

    assert len(buffer) == 0
    assert buffer.to_list() == []

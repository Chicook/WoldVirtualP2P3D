
import numpy as np
import pytest

from sbrtm_EN1_RN1 import NeuronaEntradaBasica


def create_neuron():
    return NeuronaEntradaBasica(
        input_size=3,
        output_size=2,
        semilla=42
    )


def test_backward_returns_expected_input_gradient_shape():
    neuron = create_neuron()

    x = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])

    neuron.forward(x)

    gradient = np.ones((2, 2))
    result = neuron.backward(gradient, x)

    assert result.shape == (2, 3)
    assert neuron.contador_backward == 1


def test_backward_rejects_invalid_gradient_shape():
    neuron = create_neuron()

    x = np.ones((2, 3))
    neuron.forward(x)

    invalid_gradient = np.ones((2, 3))

    with pytest.raises(ValueError, match="Invalid gradient shape"):
        neuron.backward(invalid_gradient, x)


def test_backward_rejects_nan_gradient():
    neuron = create_neuron()

    x = np.ones((1, 3))
    neuron.forward(x)

    invalid_gradient = np.array([[np.nan, 1.0]])

    with pytest.raises(ValueError, match="NaN or infinite"):
        neuron.backward(invalid_gradient, x)


def test_backward_rejects_infinite_gradient():
    neuron = create_neuron()

    x = np.ones((1, 3))
    neuron.forward(x)

    invalid_gradient = np.array([[np.inf, 1.0]])

    with pytest.raises(ValueError, match="NaN or infinite"):
        neuron.backward(invalid_gradient, x)


def test_backward_supports_single_sample_gradient():
    neuron = create_neuron()

    x = np.array([[1.0, 2.0, 3.0]])
    neuron.forward(x)

    gradient = np.array([0.5, 0.8])
    result = neuron.backward(gradient, x)

    assert result.shape == (1, 3)

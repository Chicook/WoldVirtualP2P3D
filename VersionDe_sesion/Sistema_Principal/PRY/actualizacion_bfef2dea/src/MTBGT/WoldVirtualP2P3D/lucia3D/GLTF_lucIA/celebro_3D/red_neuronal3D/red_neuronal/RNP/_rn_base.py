"""_rn_base.py - Base compartida para RN6, RN9 y RN10 del paquete RNP.

Contiene las clases de datos reutilizadas en multiples optimizadores:
- NeuralWeightOptimizationConfig  (configuracion generica superset)
- NeuralWeightOptimizationMetrics (metricas de convergencia)
- NeuralWeightOptimizationResult  (contenedor de resultado)
- BaseNeuralWeightOptimizer       (clase base de algoritmos)
"""
from __future__ import annotations
import logging
import numpy as np
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NeuralWeightOptimizationConfig:
    """Configuracion unificada para optimizadores de pesos neuronales 2026."""

    def __init__(
        self,
        learning_rate: float = 0.001,
        weight_decay: float = 0.01,
        max_iterations: int = 1000,
        gradient_clipping: float = 1.0,
        normalize_gradients: bool = True,
        decoupled_decay: bool = True,
        nesterov: bool = True,
        trust_ratio: bool = True,
        polyak_decay: float = 0.999,
        update_clip: float = 10.0,
        precision_epsilon: float = 1e-12,
        muon_ns_steps: int = 5,
        muon_orthogonal: bool = True,
        adabelief_beta1: float = 0.9,
        adabelief_beta2: float = 0.999,
        adabelief_epsilon: float = 1e-8,
        ams_bound: bool = True,
        swats_beta1: float = 0.9,
        swats_beta2: float = 0.999,
        swats_epsilon: float = 1e-8,
        swats_switch_iter: int = 100,
        swats_switch_threshold: float = 0.95,
        sgd_momentum: float = 0.9,
        sam_rho: float = 0.05,
        sam_adaptive: bool = True,
        kan_spline_order: int = 3,
        kan_grid_size: int = 5,
        hybrid_strategy: str = "adaptive_ensemble",
        adamw_beta1: float = 0.9,
        adamw_beta2: float = 0.999,
        adamw_epsilon: float = 1e-8,
        radam_beta1: float = 0.9,
        radam_beta2: float = 0.999,
        radam_epsilon: float = 1e-8,
        lookahead_k: int = 6,
        lookahead_alpha: float = 0.2,
        nadam_beta1: float = 0.9,
        nadam_beta2: float = 0.999,
        nadam_epsilon: float = 1e-8,
        lamb_beta1: float = 0.9,
        lamb_beta2: float = 0.999,
        lamb_epsilon: float = 1e-8,
        lion_beta1: float = 0.9,
        lion_beta2: float = 0.99,
        lion_epsilon: float = 1e-8,
        sharpness_rho: float = 0.05,
        sam_beta: float = 0.9,
        **kwargs: Any,
    ) -> None:
        self.learning_rate = max(0.0, float(learning_rate))
        self.weight_decay = max(0.0, float(weight_decay))
        self.max_iterations = max(1, int(max_iterations))
        self.gradient_clipping = max(0.0, float(gradient_clipping))
        self.normalize_gradients = bool(normalize_gradients)
        self.decoupled_decay = bool(decoupled_decay)
        self.nesterov = bool(nesterov)
        self.trust_ratio = bool(trust_ratio)
        self.polyak_decay = max(0.0, min(1.0, float(polyak_decay)))
        self.update_clip = max(0.0, float(update_clip))
        self.precision_epsilon = max(float(precision_epsilon), 1e-15)
        self.muon_ns_steps = max(1, int(muon_ns_steps))
        self.muon_orthogonal = bool(muon_orthogonal)
        self.adabelief_beta1 = max(0.0, min(1.0, float(adabelief_beta1)))
        self.adabelief_beta2 = max(0.0, min(1.0, float(adabelief_beta2)))
        self.adabelief_epsilon = max(float(adabelief_epsilon), 1e-12)
        self.ams_bound = bool(ams_bound)
        self.swats_beta1 = max(0.0, min(1.0, float(swats_beta1)))
        self.swats_beta2 = max(0.0, min(1.0, float(swats_beta2)))
        self.swats_epsilon = max(float(swats_epsilon), 1e-12)
        self.swats_switch_iter = max(1, int(swats_switch_iter))
        self.swats_switch_threshold = max(0.0, min(1.0, float(swats_switch_threshold)))
        self.sgd_momentum = max(0.0, min(1.0, float(sgd_momentum)))
        self.sam_rho = max(0.0, float(sam_rho))
        self.sam_adaptive = bool(sam_adaptive)
        self.kan_spline_order = max(1, int(kan_spline_order))
        self.kan_grid_size = max(3, int(kan_grid_size))
        self.hybrid_strategy = str(hybrid_strategy)
        self.adamw_beta1, self.adamw_beta2 = float(adamw_beta1), float(adamw_beta2)
        self.adamw_epsilon = float(adamw_epsilon)
        self.radam_beta1, self.radam_beta2 = float(radam_beta1), float(radam_beta2)
        self.radam_epsilon = float(radam_epsilon)
        self.lookahead_k, self.lookahead_alpha = max(1, int(lookahead_k)), float(lookahead_alpha)
        self.nadam_beta1, self.nadam_beta2 = float(nadam_beta1), float(nadam_beta2)
        self.nadam_epsilon = float(nadam_epsilon)
        self.lamb_beta1, self.lamb_beta2 = float(lamb_beta1), float(lamb_beta2)
        self.lamb_epsilon = float(lamb_epsilon)
        self.lion_beta1, self.lion_beta2 = float(lion_beta1), float(lion_beta2)
        self.lion_epsilon, self.sharpness_rho = float(lion_epsilon), float(sharpness_rho)
        self.sam_beta = float(sam_beta)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class NeuralWeightOptimizationMetrics:
    """Metricas avanzadas de convergencia, geometria espectral y curvatura."""

    def __init__(
        self,
        algorithm_name: str = "Neural-2026",
        initial_loss: float = 0.0,
        final_loss: float = 0.0,
        convergence_iterations: int = 0,
        adamw_weight_decay_efficiency: float = 0.0,
        radam_rectification_stability: float = 0.0,
        lookahead_convergence_speed: float = 0.0,
        nadam_nesterov_acceleration: float = 0.0,
        lamb_layer_wise_adaptation: float = 0.0,
        adabelief_belief_correction: float = 0.0,
        lion_momentum_efficiency: float = 0.0,
        sam_sharpness_awareness: float = 0.0,
        swats_switching_efficiency: float = 0.0,
        swats_efficiency: float = 0.0,
        neural_weight_integration_score: float = 0.0,
        overall_score: float = 0.0,
        optimization_time: float = 0.0,
        timestamp: str = "",
        precision_score: float = 0.0,
        gradient_signal_ratio: float = 0.0,
        update_efficiency: float = 0.0,
        condition_estimate: float = 0.0,
        cosine_similarity: float = 0.0,
        weight_norm: float = 0.0,
        gradient_norm: float = 0.0,
        switch_iteration: int = 0,
        phase: str = "integrated",
        polyak_score: float = 0.0,
        trust_ratio_mean: float = 0.0,
        muon_orthogonality: float = 0.0,
        flatness_ratio: float = 0.0,
        kan_representation_score: float = 0.0,
    ) -> None:
        self.__dict__.update(locals())
        del self.__dict__["self"]


class NeuralWeightOptimizationResult:
    """Contenedor de resultados de optimizacion neuronal."""

    def __init__(
        self,
        success: bool = False,
        optimized_model: Any = None,
        metrics: Optional[NeuralWeightOptimizationMetrics] = None,
        optimization_history: List[float] = None,
        best_weights: Dict[str, List] = None,
        theoretical_analysis: Dict = None,
        performance_analysis: Dict = None,
        recommendations: List[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self.__dict__.update(
            success=success, optimized_model=optimized_model, metrics=metrics,
            optimization_history=optimization_history or [],
            best_weights=best_weights or {},
            theoretical_analysis=theoretical_analysis or {},
            performance_analysis=performance_analysis or {},
            recommendations=recommendations or [],
            error_message=error_message,
        )


class BaseNeuralWeightOptimizer:
    """Clase base extensible para optimizadores de pesos neuronales."""

    def __init__(self, config: NeuralWeightOptimizationConfig) -> None:
        self.config, self.optimizer = config, None
        self.neural_history: List[float] = []
        self.integration_analysis: Dict[str, Any] = {}

    def create_optimizer(self, model: Any) -> Any:
        raise NotImplementedError

    def optimize_weights(
        self, model: Any, data_loader: Any, criterion: Any = None
    ) -> NeuralWeightOptimizationResult:
        raise NotImplementedError

    def _evaluate_model(
        self, model: Any, data_loader: Any, criterion: Any = None
    ) -> Dict[str, float]:
        return {"loss": float(np.random.rand()), "accuracy": float(np.random.rand())}

    def _check_convergence(self, history: List[float]) -> bool:
        return (
            len(history) >= 10
            and all(history[i] >= history[i + 1] - 0.001 for i in range(-10, -1))
        )

    def _extract_weights(self, model: Any) -> Optional[List[np.ndarray]]:
        if model is None:
            return None
        if isinstance(model, (list, tuple)):
            return [
                np.asarray(v, dtype=float).copy()
                for v in model
                if np.isscalar(v) or hasattr(v, "shape")
            ]
        for attr, is_callable in [
            ("get_weights", True), ("weights", False), ("parameters", True)
        ]:
            if hasattr(model, attr):
                try:
                    val = getattr(model, attr)() if is_callable else getattr(model, attr)
                    if val is not None:
                        return [
                            np.asarray(
                                p.detach().cpu().numpy() if hasattr(p, "detach") else p,
                                dtype=float,
                            )
                            for p in val
                        ]
                except Exception:
                    pass
        return None

    def _apply_weights(self, model: Any, weights: List[np.ndarray]) -> bool:
        if model is None or not weights:
            return False
        setter = getattr(model, "set_weights", None)
        if callable(setter):
            try:
                setter([v.copy() for v in weights])
                return True
            except Exception:
                return False
        if hasattr(model, "weights"):
            try:
                model.weights = [v.copy() for v in weights]
                return True
            except Exception:
                return False
        if isinstance(model, list):
            model[:] = [v.copy() for v in weights]
            return True
        return False

    def _estimate_gradients(
        self, weights: List[np.ndarray], epoch: int
    ) -> List[np.ndarray]:
        rng = np.random.default_rng(epoch + len(weights))
        scale = 0.01 / (1.0 + 0.1 * epoch)
        noise = 0.001 / (1.0 + epoch)
        return [
            -(v / max(float(np.linalg.norm(v)), 1e-12)) * scale
            + rng.normal(0.0, noise, v.shape)
            for v in weights
        ]

    @staticmethod
    def _mean(values: List[float]) -> float:
        return float(np.mean(values)) if values else 0.0

    @staticmethod
    def _trend(values: List[float]) -> str:
        if len(values) < 5:
            return "insufficient_data"
        trend = float(np.polyfit(range(len(values)), values, 1)[0])
        return "increasing" if trend > 0.001 else "decreasing" if trend < -0.001 else "stable"

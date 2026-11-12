"""_sl_math.py - Biblioteca unificada de precision matematica neuronal 2026.

Contiene MathematicalPrecision2026 y MathematicalPrecision compartido para SL1..SL10.
"""
from typing import Tuple, List, Optional, Any
import numpy as np


class MathematicalPrecision2026:
    """Utilidades unificadas de precision matematica neuronal 2026."""

    EPS: float = 1e-12



    @staticmethod
    def adabound_step(G: np.ndarray, m: np.ndarray, v: np.ndarray,
                      beta1: float, beta2: float, lr: float, final_lr: float,
                      gamma: float, eps: float, t: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula el paso AdaBound con clipping dinamico entre cotas inferior y superior."""
        new_m = beta1 * m + (1.0 - beta1) * G
        new_v = beta2 * v + (1.0 - beta2) * (G ** 2)
        bias_corr1 = 1.0 - (beta1 ** t)
        bias_corr2 = 1.0 - (beta2 ** t)
        m_hat = new_m / max(bias_corr1, MathematicalPrecision2026.EPS)
        v_hat = new_v / max(bias_corr2, MathematicalPrecision2026.EPS)

        # Limites dinamicos dependientes del paso t
        lower_bound = final_lr * (1.0 - 1.0 / (gamma * t + 1.0))
        upper_bound = final_lr * (1.0 + 1.0 / (gamma * t))
        step_size = lr / (np.sqrt(v_hat) + eps)
        bounded_step_size = np.clip(step_size, lower_bound, upper_bound)
        step = bounded_step_size * m_hat
        return step, new_m, new_v




    @staticmethod
    def adadelta_step(G: np.ndarray, mean_sq_g: np.ndarray, mean_sq_d: np.ndarray,
                      rho: float, eps: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Paso canonico AdaDelta con consistencia dimensional [Delta x] ~ [Delta x]."""
        new_sq_g = rho * mean_sq_g + (1.0 - rho) * (G ** 2)
        rms_d = np.sqrt(mean_sq_d + eps)
        rms_g = np.sqrt(new_sq_g + eps)
        delta = -(rms_d / rms_g) * G
        new_sq_d = rho * mean_sq_d + (1.0 - rho) * (delta ** 2)
        return delta, new_sq_g, new_sq_d




    @staticmethod
    def adagrad_norm_step(G: np.ndarray, b_t: float, lr: float, eps: float) -> Tuple[np.ndarray, float]:
        """AdaGrad-Norm (Ward 2020-2026): actualizacion escalonada por norma global."""
        g_norm_sq = float(np.sum(G ** 2))
        new_b = b_t + g_norm_sq
        step_size = lr / (math.sqrt(new_b) + eps)
        return step_size * G, new_b




    @staticmethod
    def adam_step(G: np.ndarray, m: np.ndarray, v: np.ndarray,
                  beta1: float, beta2: float, eps: float, t: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula el paso Adam con correccion exacta de sesgo."""
        new_m = beta1 * m + (1.0 - beta1) * G
        new_v = beta2 * v + (1.0 - beta2) * (G ** 2)
        bias_corr1 = 1.0 - (beta1 ** t)
        bias_corr2 = 1.0 - (beta2 ** t)
        m_hat = new_m / max(bias_corr1, MathematicalPrecision2026.EPS)
        v_hat = new_v / max(bias_corr2, MathematicalPrecision2026.EPS)
        return m_hat / (np.sqrt(v_hat) + eps), new_m, new_v




    @staticmethod
    def adamax_step(G: np.ndarray, m: np.ndarray, u: np.ndarray,
                    beta1: float, beta2: float, eps: float, t: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula el paso Adamax exacto con norma infinita y correccion de sesgo."""
        new_m = beta1 * m + (1.0 - beta1) * G
        new_u = np.maximum(beta2 * u, np.abs(G))
        bias_corr = 1.0 - (beta1 ** t)
        m_hat = new_m / max(bias_corr, MathematicalPrecision2026.EPS)
        step = m_hat / (new_u + eps)
        return step, new_m, new_u




    @staticmethod
    def adaptive_epsilon(G: np.ndarray, base_eps: float = 1e-8) -> float:
        """Epsilon adaptativo segun la escala y cota espectral del gradiente."""
        g_norm = float(np.linalg.norm(G))
        scale = math.sqrt(max(G.size, 1))
        return max(base_eps, (g_norm / scale) * 1e-5)




    @staticmethod
    def amsgrad_step(G: np.ndarray, m: np.ndarray, v: np.ndarray, v_max: np.ndarray,
                     beta1: float, beta2: float, eps: float, t: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Calcula el paso AMSGrad con segundo momento monotonico no decreciente."""
        new_m = beta1 * m + (1.0 - beta1) * G
        new_v = beta2 * v + (1.0 - beta2) * (G ** 2)
        new_v_max = np.maximum(v_max, new_v)
        bias_corr = 1.0 - (beta1 ** t)
        m_hat = new_m / max(bias_corr, MathematicalPrecision2026.EPS)
        step = m_hat / (np.sqrt(new_v_max) + eps)
        return step, new_m, new_v, new_v_max




    @staticmethod
    def centered_rms_update(G: np.ndarray, mean_g: np.ndarray, mean_sq: np.ndarray,
                            alpha: float, eps: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula RMS centrado (Graves) estimando media y varianza desacopladas."""
        new_mean_g = alpha * mean_g + (1.0 - alpha) * G
        new_mean_sq = alpha * mean_sq + (1.0 - alpha) * (G ** 2)
        variance = np.maximum(new_mean_sq - (new_mean_g ** 2), 0.0)
        scaled_g = G / (np.sqrt(variance) + eps)
        return scaled_g, new_mean_g, new_mean_sq



        @staticmethod
        def cosine_decay(step: int, max_steps: int, min_ratio: float = 0.01) -> float:
            """Decaimiento cosenoidal suave para tasa de aprendizaje."""
            progress = min(max(step / max(max_steps, 1), 0.0), 1.0)
            return min_ratio + 0.5 * (1.0 - min_ratio) * (1.0 + math.cos(math.pi * progress))
    # ===========================================================================
    # 2. MOTOR INTERNO DEL SISTEMA INTEGRADO 2026
    # ===========================================================================
    class IntegratedSupervisedLearningOptimizerInternal:
        """Motor de orquestacion y ensamble de optimizadores neuronales 2026."""




    @staticmethod
    def cosine_warm_restart(t: int, T_0: int = 10, T_mult: int = 2,
                            eta_min: float = 1e-5, eta_max: float = 1e-1) -> float:
        """SGDR: Tasa de aprendizaje coseno con reinicios calientes periodicos."""
        curr_T = T_0
        t_curr = t
        while t_curr >= curr_T:
            t_curr -= curr_T
            curr_T *= T_mult
        return eta_min + 0.5 * (eta_max - eta_min) * (1.0 + math.cos(math.pi * (t_curr / max(curr_T, 1))))




    @staticmethod
    def decayed_accumulator(G_sq: np.ndarray, G: np.ndarray,
                            decay: float = 0.9995) -> np.ndarray:
        """Acumulador AdaGrad con decaimiento debil para evitar estancamiento prematuro."""
        return decay * G_sq + (G ** 2)




    @staticmethod
    def gsnr(G: np.ndarray, G_sq: np.ndarray, t: int) -> float:
        """Gradient Signal-to-Noise Ratio (GSNR): signal / (noise + eps)."""
        g_sq_mean = G_sq / max(t, 1)
        g_mean_sq = (G / max(t, 1)) ** 2
        noise     = np.sum(np.maximum(g_sq_mean - g_mean_sq, 0.0))
        return float(np.sum(g_mean_sq) / (noise + MathematicalPrecision2026.EPS))




    @staticmethod
    def newton_schulz5(G: np.ndarray, steps: int = 5) -> np.ndarray:
        """Ortogonalizacion Newton-Schulz grado-5 (Muon 2026). Aproxima factor U de G=USV^T sin SVD."""
        assert G.ndim == 2, "newton_schulz5 requiere matriz 2D"
        X = G / (np.linalg.norm(G, ord="fro") + MathematicalPrecision2026.EPS)
        a, b = 1.5, -0.5
        for _ in range(steps):
            X = a * X + b * X @ (X.T @ X)
        return X




    @staticmethod
    def polyak_average(avg: np.ndarray, current: np.ndarray,
                       decay: float = 0.999) -> np.ndarray:
        """EMA Polyak averaging de pesos."""
        return decay * avg + (1.0 - decay) * current




    @staticmethod
    def polyak_step(P: np.ndarray, W: np.ndarray, decay: float = 0.999) -> np.ndarray:
        """Polyak-Ruppert parameter averaging con decaimiento exponencial."""
        return decay * P + (1.0 - decay) * W




    @staticmethod
    def sign_sgd_ef21(G: np.ndarray, e: np.ndarray, lr: float) -> Tuple[np.ndarray, np.ndarray]:
        """Sign-SGD con Error Feedback 21 (EF21)."""
        d = max(G.size, 1)
        v = G + e
        p = np.sign(v)
        scale = np.sum(np.abs(v)) / d
        return lr * scale * p, v - scale * p




    @staticmethod
    def soap_precondition(G: np.ndarray, L: np.ndarray, R: np.ndarray,
                          beta: float = 0.95) -> np.ndarray:
        """SOAP Shampoo-style: actualiza curvatura L/R con EMA y aplica P=L^{-1/2} G R^{-1/2}."""
        m, n = G.shape
        L[:] = beta * L + (1 - beta) * (G @ G.T)
        R[:] = beta * R + (1 - beta) * (G.T @ G)
        eps  = MathematicalPrecision2026.EPS
        return np.linalg.inv(L + eps * np.eye(m)) @ G @ np.linalg.inv(R + eps * np.eye(n))



    @staticmethod
    def softmax_weights(losses: np.ndarray, temperature: float = 1.0) -> np.ndarray:
        """Ponderacion Softmax inversa para meta-ensamble de optimizadores."""
        scaled = - (losses - np.min(losses)) / max(temperature, MathematicalPrecision2026.EPS)
        exp_vals = np.exp(np.clip(scaled, -50.0, 50.0))
        return exp_vals / (np.sum(exp_vals) + MathematicalPrecision2026.EPS)




    @staticmethod
    def top_k_sparsify(G: np.ndarray, density: float = 0.1) -> np.ndarray:
        """Compresion de gradiente Top-K adaptativa 2026 para comunicacion distribuida."""
        k = max(1, int(G.size * density))
        flat = np.abs(G.ravel())
        threshold = np.partition(flat, -k)[-k]
        return G * (np.abs(G) >= threshold)




    @staticmethod
    def trust_ratio_clip(update: np.ndarray, param: np.ndarray,
                         clip: float = 10.0) -> np.ndarray:
        """Trust-ratio por capa con clipping hiperbolico."""
        w_norm = np.linalg.norm(param)
        u_norm = np.linalg.norm(update)
        ratio  = (w_norm / (u_norm + MathematicalPrecision2026.EPS))
        ratio  = min(ratio, clip)
        return update * ratio


# Alias de compatibilidad
MathematicalPrecision = MathematicalPrecision2026

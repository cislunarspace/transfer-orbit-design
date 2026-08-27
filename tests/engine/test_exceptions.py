"""tests for src.engine.exceptions -- translate_exception 映射。"""

from __future__ import annotations

from src.engine.exceptions import OrbitError, translate_exception


class TestOrbitErrorAttributes:
    def test_code_and_message(self):
        e = OrbitError(code="ERR", message="msg")
        assert e.code == "ERR"
        assert e.message == "msg"
        assert e.cause is None

    def test_str(self):
        e = OrbitError(code="ERR", message="msg")
        assert "msg" in str(e)

    def test_cause_preserved(self):
        cause = ValueError("root")
        e = OrbitError(code="ERR", message="msg", cause=cause)
        assert e.cause is cause


class TestTranslateDesignNotConverged:
    def test_translate_design_not_converged(self):
        from e2m2e.algorithm.design.design_orbit import DesignNotConvergedError

        raw = DesignNotConvergedError("segmented 拼接未生成任何星历点")
        err = translate_exception(raw)
        assert err.code == "CORRECTION_DIVERGED"
        assert err.cause is raw


class TestTranslatePropagationNewContract:
    """e2m2e 5.6.6 新增类型化异常（#349/#378）的翻译。

        Translation of the typed exceptions added
    in e2m2e 5.6.6 (#349/#378)."""

    def test_translate_propagation_failure(self):
        from e2m2e.exceptions import PropagationFailure

        raw = PropagationFailure("step size collapsed to machine floor")
        err = translate_exception(raw)
        assert err.code == "PROPAGATION_FAILED"
        assert err.cause is raw

    def test_translate_rust_extension_unavailable(self):
        from e2m2e.exceptions import RustExtensionUnavailableError

        raw = RustExtensionUnavailableError("missing symbol: propagate_cr3bp")
        err = translate_exception(raw)
        assert err.code == "BACKEND_UNAVAILABLE"
        assert err.cause is raw

    def test_design_not_converged_message_carries_cause(self):
        from e2m2e.algorithm.design.design_orbit import DesignNotConvergedError
        from e2m2e.data.templates import ConvergenceState, FailureCause

        # status/cause 须一致（ResultStatus 构造校验），停滞对停滞
        # status/cause must agree (validated on ResultStatus construction): stalled maps to stalled
        raw = DesignNotConvergedError(
            "LM 停滞",
            status=ConvergenceState.STAGNATED,
            cause=FailureCause.STAGNATION_DETECTED,
        )
        err = translate_exception(raw)
        assert err.code == "CORRECTION_DIVERGED"
        assert "STAGNATION_DETECTED" in err.message



class TestTranslateBuiltins:
    def test_translate_value_error(self):
        raw = ValueError("orbit_type 必须为 DRO/DPO/NRHO")
        err = translate_exception(raw)
        assert err.code == "INVALID_PARAMS"
        assert err.cause is raw

    def test_translate_file_not_found(self):
        raw = FileNotFoundError("/path/to/kernel.tf")
        err = translate_exception(raw)
        assert err.code == "KERNEL_NOT_FOUND"
        assert err.cause is raw

    def test_translate_not_implemented(self):
        raw = NotImplementedError("Axial orbit not supported")
        err = translate_exception(raw)
        assert err.code == "NOT_IMPLEMENTED"
        assert err.cause is raw

    def test_translate_unknown(self):
        raw = RuntimeError("unexpected")
        err = translate_exception(raw)
        assert err.code == "UNKNOWN_ERROR"
        assert err.cause is raw

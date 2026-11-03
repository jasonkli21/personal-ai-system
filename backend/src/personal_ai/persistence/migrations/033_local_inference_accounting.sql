ALTER TABLE provider_invocations
    DROP CONSTRAINT provider_invocations_execution_mode_check,
    DROP CONSTRAINT provider_invocations_cost_class_check,
    ADD CONSTRAINT provider_invocations_execution_mode_check
        CHECK (execution_mode IN ('STRICT_FREE', 'EXPLICIT_BYOK', 'CHATGPT_PLAN', 'LOCAL_ONLY')),
    ADD CONSTRAINT provider_invocations_cost_class_check
        CHECK (cost_class IN ('VERIFIED_FREE', 'USER_BILLED', 'SUBSCRIPTION', 'UNKNOWN', 'LOCAL_NO_CHARGE')),
    ADD CONSTRAINT provider_invocations_local_cost_check
        CHECK ((execution_mode = 'LOCAL_ONLY') = (cost_class = 'LOCAL_NO_CHARGE'));

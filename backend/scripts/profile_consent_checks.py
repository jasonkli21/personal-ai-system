"""Run consent checks with the provider-isolation network fences."""
from provider_isolation_checks import FILES, main

FILES = [*FILES, "test_profile_consent.py", "test_auth.py", "test_account_data.py",
         "test_profile_persistence_errors.py", "test_context_planner.py"]

if __name__ == "__main__":
    raise SystemExit(main(files=FILES, runner=__file__))

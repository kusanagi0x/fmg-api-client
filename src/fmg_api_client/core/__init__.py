"""Transport-layer primitives: client, session, exceptions, models, tasks.

Workspace locking lives in :mod:`fmg_api_client.core.locking` and is
wired together with the version adapter, since the lock URLs are
version-specific.
"""

"""High-level API modules grouped by GBM resource.

Don't import these directly in user code — go through
:class:`gbm_mx_api.GbmClient`, which holds the shared HTTP session and
exposes them as attributes::

    client = GbmClient.from_session(session)
    contracts = client.contracts.list()
    accounts = client.accounts.list(contracts[0].contract_id)
    orders = client.orders.list_filled(...)
"""

"""Cliente mínimo de Odoo por XML-RPC (API externa estándar, Odoo 16/17/18)."""

from __future__ import annotations

import os
import xmlrpc.client
from typing import Any


class Odoo:
    def __init__(self, url: str, db: str, user: str, api_key: str):
        self.url, self.db, self.api_key = url.rstrip("/"), db, api_key
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(db, user, api_key, {})
        if not self.uid:
            raise RuntimeError("Odoo: autenticación fallida (revisar ODOO_USER / ODOO_API_KEY)")
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    @classmethod
    def desde_entorno(cls) -> "Odoo":
        return cls(os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USER"], os.environ["ODOO_API_KEY"])

    def _call(self, model: str, method: str, args: list, kwargs: dict | None = None, company_id: int | None = None) -> Any:
        kwargs = dict(kwargs or {})
        if company_id:
            kwargs["context"] = {**kwargs.get("context", {}), "allowed_company_ids": [company_id]}
        return self._models.execute_kw(self.db, self.uid, self.api_key, model, method, args, kwargs)

    def search_read(self, model, domain, fields, limit=50, order=None, company_id=None):
        kw = {"fields": fields, "limit": limit}
        if order:
            kw["order"] = order
        return self._call(model, "search_read", [domain], kw, company_id)

    def create(self, model, vals, company_id=None) -> int:
        return self._call(model, "create", [vals], company_id=company_id)

    def link(self, model: str, rec_id: int) -> str:
        return f"{self.url}/odoo/{model}/{rec_id}"

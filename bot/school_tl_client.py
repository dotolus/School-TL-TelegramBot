import httpx


class SchoolTLError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class SchoolTLClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        school: str,
        period: str,
        school_class: str,
        admin_password: str,
    ):
        self._http = http_client
        self._base_url = base_url
        self._dataset_path = f"{school}/{period}/{school_class}"
        self._admin_password = admin_password

    def _dataset_url(self, resource: str) -> str:
        return f"{self._base_url}/api/{self._dataset_path}/{resource}"

    def _login_url(self) -> str:
        return f"{self._base_url}/api/auth/login"

    async def _login(self) -> None:
        await self._http.post(self._login_url(), json={"password": self._admin_password})

    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            message = response.json().get("error", response.text)
        except ValueError:
            message = response.text
        raise SchoolTLError(response.status_code, message)

    async def get_timeline(self) -> list[dict]:
        response = await self._http.get(self._dataset_url("timeline"))
        if response.status_code >= 400:
            self._raise_for_error(response)
        return response.json()["items"]

    async def create_item(self, item: dict) -> dict:
        url = self._dataset_url("timeline/items")
        response = await self._http.post(url, json=item)
        if response.status_code == 401:
            await self._login()
            response = await self._http.post(url, json=item)
        if response.status_code >= 400:
            self._raise_for_error(response)
        return response.json()

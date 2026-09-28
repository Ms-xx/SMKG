import logging

from neo4j import AsyncGraphDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._driver = None
        return cls._instance

    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    async def verify_connectivity(self):
        await self.driver.verify_connectivity()

    async def close(self):
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def execute_query(self, query: str, parameters: dict = None):
        """执行只读查询并返回 dict 列表。

        neo4j 驱动 5.x 的 `AsyncResult.fetch(n)` 必须传拉取条数，直接调用会抛
        TypeError；这里优先使用 `AsyncResult.data()` 一次取全部。
        若结果对象未实现 `data()`（老驱动或部分测试替身），回退到 `fetch()`。
        """
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            data = getattr(result, "data", None)
            if callable(data):
                return list(await data())
            return [record.data() for record in await result.fetch()]

    async def execute_write(self, query: str, parameters: dict = None):
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            await result.consume()
            return True

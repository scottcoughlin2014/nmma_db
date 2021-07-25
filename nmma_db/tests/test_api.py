import string
import random
from typing import List

from nmma_db.api import app_factory


class TestAPIs(object):
    # python -m pytest -s api.py
    # python -m pytest api.py

    # test lightcurve fit api

    @staticmethod
    async def make_light_curve_fit(
        cand_name: str = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(9)
        ),
        model_name: str = "Bu2019lm",
        nmma_data: List = [[]],
    ):

        nmma_data = [['2021-06-25T05:24:12.001', 'g', '19.8632009031521', '0.128752913293544'], ['2021-06-25T06:35:42.996', 'r', '19.8133436851195', '0.131321647817597'], ['2021-06-25T09:29:06.999', 'r', '19.8861018976076', '0.119905531510047'], ['2021-06-25T10:00:27.003', 'i', '20.2030047292301', '0.225722913404512'], ['2021-06-25T10:59:24.996', 'g', '19.7775414755215', '0.16234159304903'], ['2021-06-26T05:29:25.002', 'g', '19.9184297288699', '0.13630028984291'], ['2021-06-26T06:28:03.996', 'r', '20.3180923886158', '0.185063773401895'], ['2021-06-26T07:50:40.998', 'r', '20.1278004960138', '0.132642594373114']] 

        return {
            "cand_name": cand_name,
            "model_name": model_name,
            "nmma_data": nmma_data,
        }

    async def test_light_curve_fit(self, aiohttp_client):
        """Test saving and retrieving a lightcurve fit: /api/fit

        :param aiohttp_client:
        :return:
        """

        client = await aiohttp_client(await app_factory())

        light_curve_fit = await self.make_light_curve_fit()

        # post
        resp = await client.post(
            "/api/fit", json=light_curve_fit, timeout=600
        )

        assert resp.status == 200
        result = await resp.json()
        assert result["status"] == "success"
        assert "message" in result

        # post
        resp = await client.get(
            "/api/fit", json=light_curve_fit, timeout=5
        )

        assert resp.status == 200
        result = await resp.json()
        assert result["status"] == "success"
        assert "message" in result

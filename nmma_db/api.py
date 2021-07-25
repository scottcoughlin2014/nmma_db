from abc import ABC
from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, ReDocUiSettings
from bson.json_util import dumps
from odmantic import Model
from sqlalchemy.orm.exc import NoResultFound
from typing import List, Mapping, Optional
import uvloop

from nmma_db.models import DBSession, init_db, LightcurveFit
from nmma_db.fit import fit_lc
from nmma_db.utils import load_config

cfg = load_config(config_file="config.yaml")["nmma"]


class Handler:
    @staticmethod
    def success(message: str = "", data: Optional[Mapping] = None):
        response = {"status": "success", "message": message}
        if data is not None:
            response["data"] = data
        return web.json_response(response, status=200, dumps=dumps)

    @staticmethod
    def error(message: str = "", status: int = 400):
        return web.json_response({"status": "error", "message": message}, status=status)


# @routes.get('/', name='ping', allow_head=False)
async def ping(request: web.Request) -> web.Response:
    """
    ping/pong

    :param request:
    :return:

    ---
    summary: ping/pong
    tags:
      - root

    responses:
      '200':
        description: greetings to ... anyone
        content:
          application/json:
            schema:
              type: object
              required:
                - status
                - message
              properties:
                status:
                  type: string
                message:
                  type: string
            example:
              status: success
              message: greetings from NMMA!
    """
    return web.json_response(
        {"status": "success", "message": "greetings from NMMA!"}, status=200
    )


class LightcurveFitModel(Model, ABC):
    """Data model for light curve fitter for streamlined validation"""

    model_name: str
    cand_name: str
    nmma_data: List[List[str]]


class LightcurveFitHandler(Handler):
    """Handlers to work with light curves"""

    def __init__(self, test: bool = False):
        """Constructor for light curve class

        :param test: is this a test?
        :return:
        """

        self.test = test

    async def post(self, request: web.Request) -> web.Response:
        """Trigger light curve fitting

        :param request:
        :return:
        ---
        summary: Trigger light curve fitting
        tags:
          - lightcurvefits

        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
        responses:
          '200':
            description: queue submitted
            content:
              application/json:
                schema:
                  type: object
          '400':
            description: query parsing/execution error
            content:
              application/json:
                schema:
                  type: object
        """

        _data = await request.json()

        # validate
        LightcurveFitModel(**_data)

        if self.test:
            return self.success(message="submitted")

        model_name = _data.get("model_name")
        cand_name = _data.get("cand_name")
        nmma_data = _data.get("nmma_data")

        try:
            lcfit = LightcurveFit.query.filter_by(
                model_name=model_name, object_id=cand_name
            ).one()
        except NoResultFound:
            lcfit = LightcurveFit(object_id=cand_name, model_name=model_name)
            lcfit.status = lcfit.Status.WORKING
            DBSession().commit()

        if not lcfit.status == LightcurveFit.Status.READY:
            (
                posterior_samples,
                bestfit_params,
                bestfit_lightcurve,
                log_bayes_factor,
            ) = fit_lc(model_name, cand_name, nmma_data)

            lcfit.posterior_samples = posterior_samples.to_json()
            lcfit.bestfit_lightcurve = bestfit_lightcurve.to_json()
            lcfit.log_bayes_factor = log_bayes_factor
            lcfit.status = LightcurveFit.Status.READY

            DBSession().merge(lcfit)
            DBSession().commit()

            return self.success(message="submitted")
        else:
            return self.error(message="fit already exists")

    async def get(self, request: web.Request) -> web.Response:
        """Retrieve fit by candidate and model name

        :param request:
        :return:
        ---
        summary: Retrieve candidate fits
        tags:
          - lightcurvefits

        responses:
          '200':
            description: retrieved fit data
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - status
                    - message
                    - data
                  properties:
                    status:
                      type: string
                      enum: [success]
                    message:
                      type: string
                    data:
                      type: object

          '400':
            description: retrieval failed or internal/unknown cause of failure
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - status
                    - message
                  properties:
                    status:
                      type: string
                      enum: [error]
                    message:
                      type: string
                example:
                  status: error
                  message: "failure: <error message>"
        """
        _data = await request.json()

        model_name = _data.get("model_name")
        cand_name = _data.get("cand_name")

        lcfit = LightcurveFit.query.filter_by(
            model_name=model_name, object_id=cand_name
        ).one()

        if lcfit is not None:
            if not lcfit.status == LightcurveFit.Status.READY:
                return self.error(
                    message=f"Fit {model_name} of {cand_name} still running..."
                )
            else:
                return self.success(
                    message=f"Retrieved fit {model_name} of {cand_name}",
                    data=lcfit.to_dict(),
                )
        return self.error(message=f"Fit {model_name} of {cand_name} not found")


async def app_factory():
    """
        App Factory
    :return:
    """

    # init app with auth and error handling middlewares
    app = web.Application()
    app.session = init_db(
        **cfg["database"],
        autoflush=False,
        engine_args={"pool_size": 10, "max_overflow": 15, "pool_recycle": 3600},
    )

    # OpenAPI docs:
    s = SwaggerDocs(
        app,
        redoc_ui_settings=ReDocUiSettings(path="/docs/api/"),
        # swagger_ui_settings=SwaggerUiSettings(path="/docs/api/"),
        validate="False",
        title="NMMADB",
        version="0.0.1",
        description="NMMA DB: bringing light curve fitting to the light",
    )

    # instantiate handler classes:
    fit_handler = LightcurveFitHandler()

    # add routes manually
    s.add_routes(
        [
            web.get("/", ping, name="root", allow_head=False),
            # fits:
            web.post("/api/fit", fit_handler.post),
            web.get("/api/fit", fit_handler.get),
        ]
    )

    return app


uvloop.install()

if __name__ == "__main__":

    web.run_app(app_factory(), port=cfg["server"]["port"])

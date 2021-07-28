from abc import ABC
from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, ReDocUiSettings
from bson.json_util import dumps
import datetime
import jwt
from odmantic import Model
from sqlalchemy.orm.exc import NoResultFound
from typing import List, Mapping, Optional
import uvloop

from nmma_db.middlewares import (
    auth_middleware,
    error_middleware,
    auth_required,
    admin_required,
)
from nmma_db.models import DBSession, init_db, LightcurveFit, User
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


def is_admin(username: str):
    """Check if user is admin
    note: may want to change the logic to allow multiple users to be admins

    :param username:
    """
    return username == cfg["server"]["admin_username"]


class PingHandler(Handler):
    """Handler to ping the DB and check auth"""

    @auth_required
    async def get(self, request: web.Request) -> web.Response:
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
        return self.success(message="greetings from NMMA!")


class AuthHandler(Handler):
    """Handlers to work with token authentication"""

    async def post(self, request: web.Request) -> web.Response:
        """
        Authentication

        ---
        summary: Get access token
        tags:
          - auth

        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                required:
                  - username
                  - password
                properties:
                  username:
                    type: string
                  password:
                    type: string
              example:
                username: user
                password: PwD

        responses:
          '200':
            description: access token
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - status
                    - token
                  properties:
                    status:
                      type: string
                    token:
                      type: string
                example:
                  status: success
                  token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYWRtaW4iLCJleHAiOjE1OTE1NjE5MTl9.2emEp9EKf154WLJQwulofvXhTX7L0s9Y2-6_xI0Gx8w

          '400':
            description: username or password missing in requestBody
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
                examples:
                  missing username:
                    value:
                      status: error
                      message: missing username
                  missing password:
                    value:
                      status: error
                      message: missing password

          '401':
            description: bad credentials
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
                  status: error
                  message: wrong credentials

          '500':
            description: internal/unknown cause of failure
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
                  status: error
                  message: auth failed
        """
        try:
            post_data = await request.json()
        except AttributeError:
            post_data = await request.post()

        # must contain 'username' and 'password'
        if ("username" not in post_data) or (len(post_data["username"]) == 0):
            return self.error(message="missing username", status=400)
        if ("password" not in post_data) or (len(post_data["password"]) == 0):
            return self.error(message="missing password", status=400)

        username = str(post_data["username"])
        password = str(post_data["password"])

        # user exists and passwords match?
        user = User.query.filter_by(username=username).first()
        if user is None:
            return self.error("User not found", status=404)
        if user.check_password(password):
            payload = {
                "user_id": username,
                "created_at": datetime.datetime.utcnow().strftime(
                    "%Y-%m-%dT%H:%M:%S.%f+00:00"
                ),
            }
            # optionally set expiration date
            if request.app["JWT"]["JWT_EXP_DELTA_SECONDS"] is not None:
                payload["exp"] = (
                    datetime.datetime.utcnow()
                    + datetime.timedelta(
                        seconds=request.app["JWT"]["JWT_EXP_DELTA_SECONDS"]
                    )
                ).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
            jwt_token = jwt.encode(
                payload=payload,
                key=request.app["JWT"]["JWT_SECRET"],
                algorithm=request.app["JWT"]["JWT_ALGORITHM"],
            ).decode("ascii")
            return self.success(data={"token": jwt_token})

        else:
            return self.error("wrong credentials", status=401)


class UserHandler(Handler):
    """Handlers to work with Users"""

    @admin_required
    async def post(self, request: web.Request) -> web.Response:
        """
        Add new user

        :return:

        ---
        summary: Add new user
        tags:
          - users

        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                required:
                  - username
                  - password
                properties:
                  username:
                    type: string
                  password:
                    type: string
                  email:
                    type: string
              example:
                username: noone
                password: nopas!
                email: user@caltech.edu

        responses:
          '200':
            description: added user
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
                      enum: [success]
                    message:
                      type: string
                example:
                  status: success
                  message: added user noone

          '400':
            description: username or password missing in requestBody
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
                  message: username and password must be set

        """
        _data = await request.json()

        username = _data.get("username", "")
        password = _data.get("password", "")
        email = _data.get("email", None)

        if len(username) == 0 or len(password) == 0:
            return web.json_response(
                {"status": "error", "message": "username and password must be set"},
                status=400,
            )

        try:
            user = User.query.filter_by(username=username).one()
        except NoResultFound:
            user = User(username=username, email=email)
            user.set_password(password=password)
            DBSession().add(user)
            DBSession().commit()

            return self.success(message="user created")
        else:
            return self.error(message="user already exists")

    @admin_required
    async def delete(self, request: web.Request) -> web.Response:
        """
        Remove user

        :return:

        ---
        summary: Remove user
        tags:
          - users

        responses:
          '200':
            description: removed user
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
                      enum: [success]
                    message:
                      type: string
                example:
                  status: success
                  message: removed user noone

          '400':
            description: username not found or is superuser
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
                examples:
                  attempting superuser removal:
                    value:
                      status: error
                      message: cannot remove the superuser!
                  username not found:
                    value:
                      status: error
                      message: user noone not found
        """

        # get query params
        _data = await request.json()

        username = _data.get("username", "")

        if username == cfg["server"]["admin_username"]:
            return self.error(message="cannot remove the superuser!")

        user = User.query.filter_by(username=username).first()
        if user is None:
            return self.error("User not found", status=404)

        DBSession().delete(user)
        DBSession().commit()

        return self.success(message=f"removed user {username}")

    @admin_required
    async def put(self, request: web.Request) -> web.Response:
        """
        Edit user data

        :return:

        ---
        summary: Edit user data
        tags:
          - users

        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                properties:
                  username:
                    type: string
                  password:
                    type: string
              example:
                username: noone

        responses:
          '200':
            description: edited user
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
                      enum: [success]
                    message:
                      type: string
                example:
                  status: success
                  message: edited user noone

          '400':
            description: cannot rename superuser
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
                examples:
                  attempting superuser renaming:
                    value:
                        status: error
                        message: cannot rename the superuser!
        """

        _data = await request.json()

        username = _data.get("username", "")
        password = _data.get("password", "")

        # change password:
        user = User.query.filter_by(username=username).first()
        if user is None:
            return self.error("User not found", status=404)
        user.set_password(password=password)
        DBSession().merge(user)
        DBSession().commit()

        return self.success(message=f"edited user {username}")


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

    @auth_required
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

    @auth_required
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
    app = web.Application(middlewares=[auth_middleware, error_middleware])

    app.session = init_db(
        **cfg["database"],
        autoflush=False,
        engine_args={"pool_size": 10, "max_overflow": 15, "pool_recycle": 3600},
    )

    # set up JWT for user authentication/authorization
    app["JWT"] = {
        "JWT_SECRET": cfg["server"]["JWT_SECRET_KEY"],
        "JWT_ALGORITHM": cfg["server"]["JWT_ALGORITHM"],
        "JWT_EXP_DELTA_SECONDS": cfg["server"]["JWT_EXP_DELTA_SECONDS"],
    }

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
    user_handler = UserHandler()
    auth_handler = AuthHandler()
    ping_handler = PingHandler()

    # add routes manually
    s.add_routes(
        [
            web.get("/", ping_handler.get),
            # fits:
            web.post("/api/fit", fit_handler.post),
            web.get("/api/fit", fit_handler.get),
            # users:
            web.post("/api/user", user_handler.post),
            web.delete("/api/user", user_handler.delete),
            web.put("/api/user", user_handler.put),
            # auth:
            web.post("/api/auth", auth_handler.post),
        ]
    )

    return app


uvloop.install()

if __name__ == "__main__":

    web.run_app(app_factory(), port=cfg["server"]["port"])

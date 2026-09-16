import typing
import fastapi
from hypnosis_utils.logger import getLogger
from ..services import comparator_service
from hypnosis_schemas.settings import maker as maker_settings_schema


LOGGER = getLogger("v1.maker.controllers.comparator")



ROUTER = fastapi.APIRouter(
    prefix="/comparator",
    tags=["comparator"],
)



@ROUTER.get(
    "/alternativeDict",
    response_class=fastapi.responses.JSONResponse,
)
async def getComparatorAlternativeDictByUserLevel(
    language: typing.Annotated[str, fastapi.Query()] = "es"
) -> typing.Dict[str, typing.Any]:
    LOGGER.info("[MAKER] Getting alternative dict")
    result : maker_settings_schema.ComparatorAlternativeDict = await comparator_service.getComparatorAlternativeDict(
        language=language
    )
    return fastapi.responses.JSONResponse(
        content=result.model_dump(mode="json", by_alias=True, round_trip=True),
        status_code=fastapi.status.HTTP_200_OK
    )



@ROUTER.put(
    "/alternativeDict/create",
    response_class=fastapi.Response
)
async def createComparatorAlternativeDict(
    alternativeDict: typing.Annotated[maker_settings_schema.ComparatorAlternativeDict, fastapi.Body()],
) -> typing.Dict[str, typing.Any]:
    LOGGER.info("[MAKER] Creating alternative dict")
    await comparator_service.createComparatorAlternativeDict(alternativeDict)
    return fastapi.Response(status_code=fastapi.status.HTTP_201_CREATED)
